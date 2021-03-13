# alpha-ess-web_mqtt

This service gets the webdata from the alphaess.com and publishes it via MQTT. It runs on a Raspberry Pi.

## Install the Chrome driver

```
$ sudo apt install chromium-chromedriver
$ sudo pip3 install selenium
```

## Settings

Rename the settings.py.example file into setting.py file and adapt the settings.

## MQTT output

The service will produce the following MQTT output derived from the AlphaEss.com website:

```
huis/AlphaESS/pv/solar 0.0
huis/AlphaESS/load/solar 0.6
huis/AlphaESS/battery/solar 40.0
huis/AlphaESS/feed_in/solar 0.0
huis/AlphaESS/grid_consumption/solar 0.6
```

## Thanks

Thanks to DasLezteEinhorn for the [AlphaEssMonitor.py file](https://github.com/DasLetzteEinhorn/AlphaESS_Monitor_Hass)
