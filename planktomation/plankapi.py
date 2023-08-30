import threading, json
from datetime import datetime
import paho.mqtt.client as mqtt
from loguru import logger
import RPi.GPIO as GPIO
import glob


def _direction_from_forward(forward : bool):
    return {True:"FORWARD", False:"BACKWARD"}[forward]

def logcall(func):
    def call_logger(*args, **kwargs):
        logger.debug(f"Calling {func.__name__}")
        func(*args, **kwargs)
    return call_logger

class PlanktoscopeController :
    """External API to control the Planktoscope. Can only run on the Planktoscope itself."""

    def __init__(self) -> None:
        logger.info("Initializing Planktoscope controller")
        self.last_status = {}
        self.mqtt = mqtt.Client()
        self.mqtt.on_connect = self.on_connect
        self.mqtt.on_subscribe = self.on_subscribe
        self.mqtt.on_message = self.on_message
        self.DATA_ROOT='/home/pi/data'

        GPIO.setmode(GPIO.BCM)
        GPIO.setup(21, GPIO.OUT)

        # The following is to synchronize the MQTT thread with
        # the user one. This class is not designed to support
        # instances called from multiple threads.
        self.event_message = threading.Event()
        self.last_topic = None
        self.last_payload = None

        logger.info("Starting MQTT client loop")
        self.mqtt.connect("localhost",1883)
        self.mqtt.loop_start()
        self.event_message.wait() # Waiting for subscriptions


    def on_connect(self, client, userdata, flags, rc):
        logger.info("Subscribing to statuses")
        self.mqtt.subscribe('status/#')

    def on_subscribe(self, client, obj, mid, granted_qos):
        logger.info(f"Subscribed to status messages")
        self.event_message.set() # notify that subscription are done
        self.event_message.clear()

    @logcall
    def switch_light(self, on : bool):
        if (on) :
            GPIO.output(21, GPIO.HIGH)
        else:
            GPIO.output(21, GPIO.LOW)

    @logcall
    def shutter_speed(self, speed_us : int):
        self._clear_last()
        self.mqtt.publish('imager/image',f'{{"action":"settings","settings":{{"shutter_speed":{speed_us}}}}}')
        self.wait_for_camera_settings()

    @logcall
    def iso(self, iso : int):
        self._clear_last()
        self.mqtt.publish('imager/image',f'{{"action":"settings","settings":{{"iso":{iso}}}}}')
        self.wait_for_camera_settings()

    @logcall
    def auto_white_balance(self):
        self._clear_last()
        self.mqtt.publish('imager/image','{"action":"settings","settings":{"white_balance":"auto"}}')
        self.wait_for_camera_settings()

    @logcall
    def acquire_frames(self, nb_frames : int =10, sleep : int =1.5, volume : float =0.014, forward : bool =True):
        self.configure_imager()
        self._clear_last()
        direction = _direction_from_forward(forward)
        payload = f'{{"action":"image","sleep":{sleep},"pump_direction":"{direction}","volume":{volume},"nb_frame":{nb_frames} }}'
        self.mqtt.publish('imager/image', payload)
        self.wait_for_imager()
        
    @logcall
    def pump(self, forward : bool = True, volume_ml : int =2, flowrate_ml_min : int =2, wait : bool =True):
        self._clear_last()
        direction = _direction_from_forward(forward)
        payload = f'{{"action":"move","direction":"{direction}","volume":{volume_ml},"flowrate":{flowrate_ml_min} }}'
        self.mqtt.publish("actuator/pump", payload)
        if (wait):
            self.wait_for_pump()

    @logcall
    def segmentation(self):
        self._clear_last()
        payload = f'{"action":"segment","path":["/home/pi/data/img/2023-07-24/monitoring"],"settings":{"force":false,"recursive":true,"ecotaxa":false,"keep":true,"process_id":1} }'
        self.mqtt.publish("segmenter/segment", payload)
        self.wait_for_segmentation()

    @logcall
    def configure_imager(self):
        self._clear_last()
        payload = {"action":"update_config","config": self._imager_config()}
        self.mqtt.publish('imager/image', json.dumps(payload))
        self.wait_for_imager_config()

    @logcall
    def wait_for_segmentation(self):
        self._wait_for('status/segmenter','{"status":"Done"}')

    @logcall
    def wait_for_pump(self):
        self._wait_for('status/pump','{"status":"Done"}')

    @logcall
    def wait_for_imager(self):
        self._wait_for('status/imager','{"status":"Done"}')

    @logcall
    def wait_for_imager_config(self):
        self._wait_for('status/imager','{"status":"Config updated"}')

    @logcall
    def wait_for_camera_settings(self):
        self._wait_for('status/imager','{"status":"Camera settings updated"}')

    def on_message(self, client, userdata, msg):
        logger.debug(f"topic:{msg.topic} payload:{msg.payload}")
        self.last_status[msg.topic] = msg.payload
        self.last_payload = msg.payload.decode()
        self.last_topic = msg.topic
        self.event_message.set()
        self.event_message.clear()

    def monitoring_files_list(self):
        return glob.glob(f'{self.DATA_ROOT}/img/*/monitoring/**/*.jpg', recursive=True, )

    def _wait_for(self, topic, payload):
        logger.debug(f"Waiting for {topic} {payload}")
        while not(self.last_payload==payload and self.last_topic==topic):
            self.event_message.wait()
            logger.debug(f'received event {self.last_topic} {self.last_payload}')

    def _clear_last(self):
        self.last_payload = None
        self.last_topic = None

    def _imager_config(self):
        timestamp = datetime.now()
        odate = datetime.strftime(timestamp,'%Y-%m-%d')
        otime = datetime.strftime(timestamp,'%H:%M:%S')
        return {
        "description": {
            "sample_project": "Project's name",
            "sample_id": "Sample ID",
            "sample_uuid": "Sample UUID (Autogenerated)",
            "sample_ship": "Ship's name",
            "sample_operator": "Operator's name",
            "sample_sampling_gear": "Sampling gear used",
            "sample_concentrated_sample_volume": "Volume of concentrated sample, in mL",
            "sample_total_volume": "Total volume filtered by the net used, in L",
            "sample_dilution_factor": "Dilution factor of the sample, 0.5 if diluted by 2, 2 if concentrated by 2",
            "sample_speed_through_water": "Speed of the boat through water when sampling, in kts",
            "acq_id": "Acquisition ID",
            "acq_uuid": "Acquisition UUID (Autogenerated)",
            "acq_instrument": "Instrument type",
            "acq_instrument_id": "Instrument ID",
            "acq_celltype": "Flow cell dimension thickness, in µm",
            "acq_minimum_mesh": "Minimum filtration mesh size, in µm",
            "acq_maximum_mesh": "Maximum filtration mesh size, in µm",
            "acq_min_esd": "",
            "acq_max_esd": "",
            "acq_volume": "Pumped volume, in mL",
            "acq_imaged_volume": "Total imaged volume, in mL",
            "acq_magnification": "Optical magnification",
            "acq_fnumber_objective": "Focal length of the objective, in mm",
            "acq_camera_name": "Name of the camera used",
            "acq_nb_frame": "Number of picture taken",
            "acq_local_datetime": "Instrument local datetime",
            "acq_camera_resolution": "Resolution of the images",
            "acq_camera_iso": "ISO Number of the images",
            "acq_camera_shutter_speed": "Shutter speed of the images, in µs",
            "acq_software": "Software version number",
            "object_date": "Sample collection date (or beginning if using a net)",
            "object_time": "Sample collection time (or beginning if using a net)",
            "object_lat": "Sample collection latitude (or beginning if using a net)",
            "object_lon": "Sample collection longitude (or beginning if using a net)",
            "object_depth_min": "Sample collection minimal depth, in m",
            "object_depth_max": "Sample collection maximum depth, in m",
            "process_pixel": "Pixel imaging resolution, in µm/pixel",
            "process_datetime": "Segmentation timestamp",
            "process_id": "Segmentation ID",
            "process_uuid": "Segmentation UUID (Autogenerated)",
            "process_source": "Code source link of the executed code",
            "process_commit": "Version reference of the executed code",
            "sample_gear_net_opening": "Sample mouth opening dimension, in mm",
            "object_date_end": "Sample end collection date when using a net",
            "object_time_end": "Sample end collection time when using a net",
            "object_lat_end": "Sample end collection latitude when using a net",
            "object_lon_end": "Sample end collection longitude when using a net"
        },
        "sample_project": "monitoring",
        "sample_id": "monitoring",
        "sample_ship": "The_identifier",
        "sample_operator": "egm_plank",
        "sample_sampling_gear": "test",
        "acq_id": f'monitoring-{odate}-{otime}',
        "acq_instrument": "PlanktoScope v2.1",
        "acq_instrument_id": "Babanui Nousoki",
        "acq_celltype": 200,
        "acq_minimum_mesh": 10,
        "acq_maximum_mesh": 300,
        "acq_volume": "0.14",
        "acq_imaged_volume": "0.0252",
        "acq_magnification": 1.6,
        "acq_fnumber_objective": 16,
        "acq_camera": "HQ Camera",
        "acq_nb_frame": 10,
        "object_date": f'{odate}',
        "object_time": f'{otime}',
        "object_lat": "-90.0000",
        "object_lon": "0.0000",
        "object_depth_min": 1,
        "object_depth_max": 2,
        "process_pixel": 1.01,
        "process_source": "https://www.github.com/PlanktonPlanet/PlanktoScope",
        "process_commit": "v2.3-0-gd52e194"
        }