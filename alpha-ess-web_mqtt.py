#!/usr/bin/python3
import os
import signal
import time
import simplejson as json
import socket
import paho.mqtt.publish as mqtt_publish
import paho.mqtt.client as mqtt_client
import psutil
import os.path
import subprocess
from subprocess import PIPE, Popen

# external files/classes
import logger
import settings

#System check
ACTION_NOTHING   = 0
ACTION_RESTART   = 1

current_sec_time = lambda: int(round(time.time()))

serverStatus = {"cpuTemp": "0.0", "cpuUsage": "0.0", "totalProcesses": "0.0", "nrOfZombies": "0.0", "swapUsage": "0.0", "diskUsage": "0.0", "memUsage": "0.0"}
exit = False
pingFailCount = 0
oldTimeout = current_sec_time()
checkMsg = 'OK'
checkFail = False
checkAction = ACTION_NOTHING
checkReport = {}

hostnameToServerTopic = {
    'cb2-live':   'CB2Live',
    'rpi-home':   'RPiHome',
    'rpi-infra':  'RPiInfra',
    'rpi-video1': 'RPiVideo1',
    'rpi-video2': 'RPiVideo2'
}

hostname = socket.gethostname().lower()
serverTopic = hostnameToServerTopic[hostname]

mqttTopicCheck  = settings.MQTT_TOPIC_CHECK  % serverTopic
mqttTopicReport = settings.MQTT_TOPIC_REPORT  % serverTopic


def signal_handler(_signal, frame):
    global exit
    print('You pressed Ctrl+C!')
    exit = True


#Called by mqtt
def on_message_check(client, userdata, msgJson):
    #print("on_message_check: " + msgJson.topic + ": " + str(msgJson.payload))
    sendCheckReportToHomeLogic(checkFail, checkAction, checkMsg)


#Send the report to the Home Logic system checker
def sendCheckReportToHomeLogic(fail, action, msg):
    global checkMsg
    global checkFail
    global oldTimeout

    checkMsg = msg
    checkFail = fail
    checkReport['checkFail']   = checkFail
    checkReport['checkAction'] = checkAction
    checkReport['checkMsg']    = checkMsg
    mqtt_publish.single(mqttTopicReport, json.dumps(checkReport), qos=1, hostname=settings.MQTT_ServerIP)

    # Reset the RFLink Rx timeout timer
    oldTimeout = current_sec_time()


#Don't wait for the Home Logic system checker, report it directly
def sendFailureToHomeLogic(checkAction, checkMsg):
    sendCheckReportToHomeLogic(True, checkAction, checkMsg)


# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(("%s: MQTT Client connected successfully" % (time.ctime(time.time()))))
        client.subscribe([(mqttTopicCheck, 1)])
    else:
        print(("%s: ERROR: MQTT Client connected with result code %s " % (time.ctime(time.time()), str(rc))))


# The callback for when a PUBLISH message is received from the server
def on_message(client, userdata, msg):
    print(('ERROR: Received ' + msg.topic + ' in on_message function' + str(msg.payload)))


def getCpuTemperature():
    # Test if the i2c temp sensor exists (for example on CubieBoard2)
    if os.path.isfile("/sys/devices/platform/sunxi-i2c.0/i2c-0/0-0034/temp1_input"):

        with open('/sys/devices/platform/sunxi-i2c.0/i2c-0/0-0034/temp1_input') as f:
            for line in f:
                return (float(line.rstrip('\n')) / 1000)
    if os.path.isfile("/sys/devices/virtual/thermal/thermal_zone0/temp"):
        with open('/sys/devices/virtual/thermal/thermal_zone0/temp') as f:
            for line in f:
                return (float(line.rstrip('\n')) / 1000)
    else:
    # Otherwise use the RaspberryPi's vcgencmd temp command
        process = Popen(['vcgencmd', 'measure_temp'], stdout=PIPE)
        output, _error = process.communicate()
        return float(output[output.index(b'=') + 1:output.rindex(b"'")])


###
# Initalisation ####
###
logger.initLogger(settings.LOG_FILENAME)

# Init signal handler, because otherwise Ctrl-C does not work
signal.signal(signal.SIGINT, signal_handler)

readSensorTimer = 5  # Read sensors after 10 sec

serverTopic = hostnameToServerTopic[hostname]
print(("Script runs on host: %s, serverTopic: %s" % (hostname, serverTopic)))

# Give Home Assistant and Mosquitto the time to startup
time.sleep(2)

# First start the MQTT client
client = mqtt_client.Client()
client.on_connect = on_connect
client.on_message = on_message
client.connect(settings.MQTT_ServerIP, settings.MQTT_ServerPort, 60)
client.message_callback_add(mqttTopicCheck, on_message_check)
client.loop_start()

while not exit:
    readSensorTimer = readSensorTimer + 1
    # Read and send the sensor data every 600s=10min
    if readSensorTimer >= 6:
        readSensorTimer = 0

        # CPU temp
        cpuTemp = getCpuTemperature()
        #print ("CPU Temp: %s" % cpuTemp)

        time.sleep(1)  # 1s
        # Memory Usage
        mem = psutil.virtual_memory()
        memUsage = 100.0 - float(mem.available) / float(mem.total) * 100.0
        memUsage = round(memUsage, 1)
        #print ("Memory Usage: %2.1f %%, available: %d %%, total: %d %%" % (memUsage, mem.available, mem.total))

        time.sleep(1)  # 2s
        # Disk usage disk "/"
        diskUsage = psutil.disk_usage('/').percent
        #print ("Disk Usage: %s" % diskUsage)

        time.sleep(1)  # 3s
        # CPU Usage Meet 1 sec
        cpuUsage = psutil.cpu_percent(interval=1)
        #print ("CPU Usage: %s" % cpuUsage)
        # print ("-----")

        time.sleep(1)  # 4s
        result = subprocess.check_output('ps axo stat,ppid,pid,comm | grep -w defunct | wc -l', shell=True)
        nrOfZombies = int(result.decode().rstrip('\n'))
        #print("Nr of zombie processes: " + str(nrOfZombies))

        time.sleep(1)  # 5s
        result = subprocess.check_output('ps -A --no-headers | wc -l', shell=True)
        totalProcesses = int(result.decode().rstrip('\n'))
        #print("Total Nr of processes: " + str(totalProcesses))

        time.sleep(1)  # 6s
        #             total       used       free
        #Swap:       524284          0     524284
        result = subprocess.check_output("free | grep 'Swap'", shell=True)
        i = 0
        swap = [0] * 4
        for s in result.split():
            if s.isdigit():
                swap[i] = int(s)
                i = i + 1
        if swap[0] != 0:
            swapUsage = (swap[1] / swap[0]) * 100
            #print("swapUsage: %1.0f%%" % (swapUsage))
        else:
            swapUsage = -1
            #print("swapUsage not active")

        time.sleep(1)  # 7s
        serverStatus['cpuTemp'] = cpuTemp
        serverStatus['cpuUsage'] = cpuUsage
        serverStatus['totalProcesses'] = totalProcesses
        serverStatus['nrOfZombies'] = nrOfZombies
        serverStatus['swapUsage'] = ("%1.0f" % swapUsage)
        serverStatus['diskUsage'] = diskUsage
        serverStatus['memUsage'] = memUsage

        mqtt_publish.single("huis/Board/%s/server" % serverTopic, json.dumps(serverStatus, separators=(', ', ':')), hostname="192.168.5.248", retain=True)

        time.sleep(3)  # 3s
    # else:
    #     if hostname == 'cb2-live':
    #         # Check the RFLink Rx timeout
    #         if (current_sec_time() - oldTimeout) > 900:
    #             #Report failure to Home Logic system check
    #             sendFailureToHomeLogic(ACTION_NOTHING, '15 minutes nothing received from systemWatch, likely network interface down, going to reboot')
    #             time.sleep(2)  # Wait for message is send
    #             os.system("reboot")

        time.sleep(10)  # 10s
