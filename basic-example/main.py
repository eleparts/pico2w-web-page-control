import network
import socket
from time import sleep
from picozero import pico_temp_sensor, pico_led
import machine
import rp2
import sys

# 연결할 wifi의 ssid와 password 설정 
ssid = 'your_wifi_SSID'
password = 'your_wifi_password'

def connect():
    #Connect to WLAN
    wlan = network.WLAN(network.STA_IF)		# 피코 보드를 wifi 접속 모드로 설정
    wlan.active(True)						# wifi 활성화
    wlan.connect(ssid, password)			# 앞서 설정한 ssid, password로 wifi 연결
    
    # 연결이 완료될 때(True)까지 무한 반복하며 대기
    while wlan.isconnected() == False:
        if rp2.bootsel_button() == 1:		# boostsel 버튼 누르면 강제 종료
            sys.exit()
        print('Waiting for connection...')	# shell 출력과 led 깜빡이는 동작
        pico_led.on()
        sleep(0.5)
        pico_led.off()
        sleep(0.5)
    ip = wlan.ifconfig()[0]					# wifi 연결 성공 시 ip 출력 및 반환 
    print(f'Connected on {ip}')
    return ip 
    
def open_socket(ip):
    # Open a socket
    address = (ip, 80)
    connection = socket.socket()
    # 소켓 재사용 설정 (종종 발생하는 Address already in use 에러 방지)
    connection.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    connection.bind(address)
    connection.listen(1)
    return connection

def webpage(temperature, state):
    # 스마트폰이나 PC 브라우저에 띄워줄 HTML 화면 디자인 양식
    html = f"""
            <!DOCTYPE html>
            <html>
            <form action="./lighton">
            <input type="submit" value="Light on" />
            </form>
            <form action="./lightoff">
            <input type="submit" value="Light off" />
            </form>
            <form action="./close">
            <input type="submit" value="Stop server" />
            </form>
            <p>LED is {state}</p>
            <p>Temperature is {temperature}</p>
            </body>
            </html>
            """
    return str(html)	# 완성된 문자열 형태의 HTML 코드를 반환

def serve(connection):
    state = 'OFF'							# 상태값, led, 온도값 초기화 
    pico_led.off()
    temperature = 0
    
    while True:
        client = connection.accept()[0]		# 브라우저에서 보낸 데이터 받아오기
        request = client.recv(1024)
        request = str(request)
        try:
            request = request.split()[1]	# 브라우저에서 온 데이터 중 핵심만 남기기
        except IndexError:
            pass
        if request == '/lighton?':			# led on 버튼을 누르면, led 키고 state ON 상태로 전환
            pico_led.on()
            state = 'ON'
        elif request =='/lightoff?':		# led off 버튼을 누르면, led 끄고 state OFF 상태로 전환
            pico_led.off()
            state = 'OFF'
        elif request == '/close?':			# Stop server 버튼을 누르면, 프로그램 종
            sys.exit()
            
        temperature = pico_temp_sensor.temp	# 온도 값 받아오기
        html = webpage(temperature, state)	# 바뀐 온도 및 상태를 웹페이지에 저장
        client.send(html)
        client.close()

ip = connect()					# wifi 연결 및 내 ip 파악
connection = open_socket(ip)	# 해당 ip로 소켓 열기
serve(connection)				# 무한 루프를 돌며 웹 서버를 시작
