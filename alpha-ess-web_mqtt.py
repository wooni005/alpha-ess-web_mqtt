#!/usr/bin/python3
# -*- coding: utf-8 -*-

import os
import signal
import time
import serial
import _thread
import traceback
from queue import Queue
import json
import paho.mqtt.publish as mqtt_publish
import paho.mqtt.client as mqtt_client

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import shutil

# external files/classes
import logger
import serviceReport
import settings
import AlphaEssMonitor

sendQueue = Queue(maxsize=0)
current_sec_time = lambda: int(round(time.time()))
current_milli_time = lambda: int(round(time.time() * 1000))
oldTimeout = 0

exit = False
chromeDriver = None
monitor = None
alphaEssStatus = {}


def signal_handler(_signal, frame):
    global exit

    print('You pressed Ctrl+C!')
    exit = True


# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("MQTT Client connected successfully")
        client.subscribe([(settings.MQTT_TOPIC_OUT, 1), (settings.MQTT_TOPIC_CHECK, 1)])
    else:
        print(("ERROR: MQTT Client connected with result code %s " % str(rc)))


# The callback for when a PUBLISH message is received from the server
def on_message(client, userdata, msg):
    print(('ERROR: Received ' + msg.topic + ' in on_message function' + str(msg.payload)))


def on_message_homelogic(client, userdata, msg):
    print(msg.topic + " " + str(msg.payload))
    # topics = msg.topic.split("/")

    # deviceName = topics[2] #huis/RFXtrx/KaKu-12/out
    # cmnd = deviceName.split("-") #KaKu-12


def alphaEssThread():
    global oldTimeout
    global chromeDriver
    global monitor
    global exit

    oldTimeout = current_sec_time()

    try:
        print("Start Chrome driver")
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.binary_location = shutil.which("chromium-browser")
        chromeDriver = webdriver.Chrome(options=chrome_options, executable_path=shutil.which("chromedriver"))

    # Handle other exceptions and print the error
    except Exception as arg:
        print("%s" % str(arg))
        traceback.print_exc()

        #Report failure to Home Logic system check
        serviceReport.sendFailureToHomeLogic(serviceReport.ACTION_NOTHING, 'Failed to open Chrome driver')
        exit = True
        return

    print("Init AlphaEss monitor")
    monitor = AlphaEssMonitor.AlphaEssMonitor(settings.ALPHAESS_USERNAME, settings.ALPHAESS_PASSWORD)

    print("Start AlphaEss monitor")
    monitor.start(chromeDriver)

    # Delay after monitor start, otherwise url errors when getting data
    time.sleep(5)

    while not exit:
        try:
            # print("Get monitor data")
            monitor_data = monitor.get_data()

            for key in monitor_data:
                # print("Monitor data key: %s" % key)
                alphaEssStatus[key] = monitor_data[key]
                serviceReport.systemWatchTimer = current_sec_time()

            mqtt_publish.single("huis/AlphaEss/Web/solar", json.dumps(alphaEssStatus, separators=(', ', ':')), qos=1, hostname=settings.MQTT_ServerIP, retain=True)

            # print("Waiting %d seconds" % settings.ALPHAESS_WAIT)
            time.sleep(settings.ALPHAESS_WAIT)

            # Check if there is any message to send to AlphaEss.com
            if not sendQueue.empty():
                sendMsg = sendQueue.get_nowait()
                #print "SendMsg:", sendMsg
                if sendMsg != "":
                    print("SendMsg: Not implemented yet")

        # In case the message contains unusual data
        except ValueError as arg:
            print(arg)
            traceback.print_exc()
            time.sleep(1)

        # Quit the program by Ctrl-C
        except KeyboardInterrupt:
            print("Program aborted by Ctrl-C")
            exit()

        # Handle other exceptions and print the error
        except Exception as arg:
            print("%s" % str(arg))
            traceback.print_exc()
            time.sleep(10)


def print_time(delay):
    count = 0
    while count < 5:
        time.sleep(delay)
        count += 1
        print("%s" % (time.ctime(time.time())))


###
# Initalisation ####
###
logger.initLogger(settings.LOG_FILENAME)

# Init signal handler, because otherwise Ctrl-C does not work
signal.signal(signal.SIGINT, signal_handler)

# Give Home Assistant and Mosquitto the time to startup
time.sleep(2)

# First start the MQTT client
client = mqtt_client.Client()
client.message_callback_add(settings.MQTT_TOPIC_OUT,       on_message_homelogic)
client.message_callback_add(settings.MQTT_TOPIC_CHECK,     serviceReport.on_message_check)
client.on_connect = on_connect
client.on_message = on_message
client.connect(settings.MQTT_ServerIP, settings.MQTT_ServerPort, 60)
client.loop_start()

# Create the alphaEssThread
try:
    # thread.start_new_thread( print_time, (60, ) )
    _thread.start_new_thread(alphaEssThread, ())
except Exception:
    print("Error: unable to start the alphaEssThread")


while not exit:
    time.sleep(6)  # 60s

if monitor is not None:
    monitor.stop()
    print("Stopped AlphaEss monitor")

print("Clean exit!")
