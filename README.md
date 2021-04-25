# alpha-ess-web_mqtt

This service gets the webdata from the alphaess.com and publishes it via MQTT. It runs on a Raspberry Pi.

## Install python modules
The following python3 modules are needed:
```
$ sudo pip3 install simplejson paho-mqtt
```

## Install the Chrome driver

```
$ sudo apt install chromium-chromedriver
$ sudo pip3 install selenium
```

## Settings

Rename the settings.py.example file into setting.py file and adapt the settings.

## MQTT output

The service will produce the following MQTT JSON message based on the data of the AlphaEss.com website:

```
huis/AlphaESS/AlphaESS/solar {'pv': 0.0, 'load': 3.2, 'battery': 54.8, 'feed-in': 0.0, 'grid-consumption': 0.0}
```

## Thanks

Thanks to DasLezteEinhorn for the [AlphaEssMonitor.py file](https://github.com/DasLetzteEinhorn/AlphaESS_Monitor_Hass)
