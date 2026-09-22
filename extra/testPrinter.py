import paho.mqtt.client as mqtt
import ssl

def on_connect(client, userdata, flags, rc):
    print(f'Connected with result code {rc}')  # 0 = success

client = mqtt.Client()
client.username_pw_set('bblp', '596d2b37')
client.tls_set(cert_reqs=ssl.CERT_NONE)
client.tls_insecure_set(True)
client.on_connect = on_connect
client.connect('192.168.86.232', 8883, keepalive=10)
client.loop_start()
import time; time.sleep(3)
client.loop_stop()
