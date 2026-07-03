import network                  # 라즈베리 파이 피코의 Wi-Fi 하드웨어를 제어하고 무선 네트워크에 연결하는 모듈
import socket                   # TCP/IP 네트워크 통신을 가능하게 하여 웹 서버(소켓)를 생성하고 클라이언트 요청을 받는 모듈
from time import sleep          # 특정 시간 동안 코드 실행을 일시 정지(대기)시키는 함수 (와이파이 연결 대기 시 사용)
import machine                  # 피코의 핀(GPIO), ADC, PWM 등 칩 내부 하드웨어 제어 기능을 제공하는 모듈 (현재 코드에선 직접 미사용)
from picozero import pico_led   # pico 보드를 제어하기 쉽게 도와주는 모듈 / 그 중 LED 제어를 위해 사용합니다.
import rp2                      # pico보드에 사용된 RP2040/RP2350 전용 모듈로, PIO 제어 및 보드 상의 BOOTSEL 버튼 상태 등을 확인할 때 사용
import sys                      # 파이썬 인터프리터 제어 모듈로, 오류 발생이나 특정 상황(BOOTSEL 클릭) 시 프로그램을 안전하게 종료(sys.exit())하기 위해 사용
import random                   # 랜덤 함수를 사용하기 위한 모듈
import json                     # 피코의 데이터(딕셔너리, 리스트 등)를 브라우저가 해석할 수 있는 표준 문자열(JSON)로 변환하기 위해 사용

# [설정] 와이파이 접속 정보
ssid = 'your_wifi_SSID'
password = 'your_wifi_password'

""" 와이파이에 연결하고 할당받은 IP 주소를 반환하는 함수 """
def connect():
    wlan = network.WLAN(network.STA_IF) # 스테이션(STA) 모드로 와이파이 활성화
    wlan.active(True)
    wlan.connect(ssid, password)
    
    # 연결될 때까지 1초마다 대기
    while wlan.isconnected() == False:
        # 연결 대기 중 피코의 BOOTSEL 버튼을 누르면 프로그램 안전 종료 (디버깅용)
        if rp2.bootsel_button() == 1:
            sys.exit()
        print('Waiting for connection...')
        pico_led.blink()
        
    ip = wlan.ifconfig()[0] # 할당받은 IP 주소 추출 및 출력(쉘)
    print(f'Connected on {ip}')
    return ip
    
""" 웹 서버 구동을 위해 80번 포트를 열고 연결을 대기(Listen)하는 함수 """
def open_socket(ip):
    address = (ip, 80) # IP 주소와 HTTP 기본 포트(80) 결합
    connection = socket.socket()
    connection.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # 포트 재사용 설정
    connection.bind(address) # 소켓에 주소 바인딩
    connection.listen(1)     # 동시 접속 대기 인수 설정
    return connection

""" 0~9 중에서 중복되지 않는 4자리 무작위 정답 숫자를 생성하는 함수 """
def random_number():
    numbers = list(range(10))
    result = []
    while len(result) < 4:
        picked = random.choice(numbers)
        result.append(picked)
        numbers.remove(picked) # 뽑힌 숫자는 제거하여 중복 방지
    return result

# 게임 시작 시 최초 1회 정답 숫자 생성 및 콘솔 출력
tn1, tn2, tn3, tn4 = random_number()
print(f"정답 숫자(참고용): {tn1} {tn2} {tn3} {tn4}")

""" 사용자가 입력한 숫자와 정답을 비교하여 Strike와 Ball 수를 계산하는 함수 """
def check_numbers(n1, n2, n3, n4):
    target = [tn1, tn2, tn3, tn4]
    user = [n1, n2, n3, n4]
    
    strikes = 0
    balls = 0
    for i in range(4):
        if user[i] == target[i]:      # 숫자와 자리가 모두 일치하면 Strike
            strikes += 1
        elif user[i] in target:       # 자리는 틀렸지만 숫자가 정답에 포함되면 Ball
            balls += 1
    return strikes, balls

""" 
사용자가 접속했을 때 최초 1회 응답할 HTML 코드 구조정의 함수.
이 안에 포함된 JavaScript가 이후 피코와 AJAX(비동기) 통신을 전담합니다.
"""
def webpage():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8"> 
        <style>
            /* 1. 상단 숫자 표시부 레이아웃: 가로 정렬 및 간격 균등 분배 */
            .number-container { display: flex; justify-content: space-around; align-items: center; width: 660px; margin-bottom: 15px; }
            .number-box { font-size: 3rem; font-weight: bold; text-align: center; flex: 1; }
            
            /* 2. 버튼 패널 레이아웃: 그리드 형태로 배치하기 위해 flex-wrap 사용 */
            .matrix-container { display: flex; flex-wrap: wrap; gap: 10px; width: 660px; }
            .matrix-container button { width: calc(16.66% - 9px); padding: 10px 0; cursor: pointer; }
            
            /* 3. 리셋 버튼 스타일: 평소에는 숨겨두고(none), 게임 종료 시 스크립트로 노출 */
            #reset-btn { width: 100%; padding: 12px 0; font-size: 1.1rem; font-weight: bold; cursor: pointer; background-color: #2ecc71; color: white; border: none; border-radius: 5px; margin-top: 5px; display: none; }
            
            /* 4. 기록창 스타일: 가독성을 위해 연한 배경색과 대시 테두리 지정 */
            .history-box { width: 660px; min-height: 100px; background-color: #f8f9fa; padding: 10px; border-radius: 5px; }
            .result-item { font-size: 1.2rem; font-weight: bold; color: #2c3e50; margin: 5px 0; border-bottom: 1px dashed #ccc; padding-bottom: 5px; }
        </style>
    </head>
    <body>
    
        <div class="number-container">
            <div class="number-box" id="num1">0</div>
            <div class="number-box" id="num2">0</div>
            <div class="number-box" id="num3">0</div>
            <div class="number-box" id="num4">0</div>
        </div>

        <hr>

        <div class="matrix-container">
            <button onclick="sendAction('btn0')">0</button>
            <button onclick="sendAction('btn1')">1</button>
            <button onclick="sendAction('btn2')">2</button>
            <button onclick="sendAction('btn3')">3</button>
            <button onclick="sendAction('btn4')">4</button>
            <button onclick="sendAction('erase')">지우기 (←)</button> <button onclick="sendAction('btn5')">5</button>
            <button onclick="sendAction('btn6')">6</button>
            <button onclick="sendAction('btn7')">7</button>
            <button onclick="sendAction('btn8')">8</button>
            <button onclick="sendAction('btn9')">9</button>
            <button onclick="sendAction('submit')">제출 (↵)</button> <button id="reset-btn" onclick="sendAction('reset')">다시 시작 (R)</button>
        </div>

        <hr>
        
        <div class="history-box" id="history-box">
            <p class="result-item">게임을 시작합니다! 숫자를 입력하고 제출을 누르세요.</p>
        </div>
        
        <script>
            // 핵심 AJAX 함수: 브라우저 전체를 새로고침하지 않고 피코와 비동기 통신을 수행
            function sendAction(route) {
                // Fetch API를 이용하여 피코의 REST API 엔드포인트 요청 (예: /api/btn5)
                fetch('/api/' + route)
                    .then(response => response.json()) // 피코가 응답한 JSON 텍스트를 JS 객체(data)로 변환
                    .then(data => {
                        // 1. 피코 내부 상태값(n1~n4)을 읽어와 실시간으로 화면 상단 숫자 텍스트 변경
                        document.getElementById('num1').innerText = data.n1;
                        document.getElementById('num2').innerText = data.n2;
                        document.getElementById('num3').innerText = data.n3;
                        document.getElementById('num4').innerText = data.n4;
                        
                        // 2. 피코에 누적된 판정 기록 배열(history)을 이용해 하단 기록창을 완전히 새로 작성
                        const historyBox = document.getElementById('history-box');
                        historyBox.innerHTML = ""; // 기존 기록 초기화
                        data.history.forEach(item => {
                            // 배열의 요소들을 순회하며 새로운 HTML 문장 생성 후 추가
                            historyBox.innerHTML += `<p class="result-item">${item}</p>`;
                        });
                        
                        // 3. 게임 오버 여부 플래그(is_game_over)에 따라 리셋 버튼 노출 제어
                        const resetBtn = document.getElementById('reset-btn');
                        if (data.is_game_over) {
                            resetBtn.style.display = 'block'; // 정답을 맞추면 화면에 보임
                        } else {
                            resetBtn.style.display = 'none';  // 게임 중에는 숨김
                        }
                    });
            }

            // [사용자 편의 기능] 마우스 클릭 대신 PC 키보드 입력이 들어왔을 때의 매핑 리스너
            document.addEventListener('keydown', function(event) {
                const key = event.key.toLowerCase();
                
                if (event.key >= '0' && event.key <= '9') {
                    sendAction('btn' + event.key);     // 숫자키 0~9 대응
                } else if (event.key === 'Enter') {
                    sendAction('submit');              // 엔터 누르면 제출
                } else if (event.key === 'Backspace') {
                    sendAction('erase');               // 백스페이스 누르면 지우기
                } else if (key === 'r') {
                    sendAction('reset');               // 알파벳 R 누르면 게임 재시작
                }
            });
        </script>
    </body>
    </html>
    """
    return str(html) # 파싱된 완전한 HTML 문자열을 피코 소켓 스트림으로 반환

def serve(connection):
    """ 메인 웹 서버 루프: 클라이언트의 요청을 상시 수신하고 처리하는 함수 """
    global tn1, tn2, tn3, tn4 # 정답 변경(리셋)을 위해 글로벌 선언
    cursor = 1                # 현재 숫자가 입력될 자리의 위치 (1~4번 칸, 5는 꽉 찬 상태)
    
    # 게임 내부 상태 변수 초기화
    n1, n2, n3, n4 = 0, 0, 0, 0
    try_count = 1
    is_game_over = False
    game_history = ["게임을 시작합니다! 숫자를 입력하고 제출을 누르세요."]
    
    while True:
        # 브라우저 접속 대기 및 요청 메시지 수신
        client = connection.accept()[0]
        request = client.recv(1024)
        request = str(request)
        
        # HTTP 요청 라인에서 URI(주소 경로)만 파싱 (예: "GET /api/btn1 HTTP/1.1" -> "/api/btn1")
        try:
            request = request.split()[1]
        except IndexError:
            pass
        
        # 주소 앞뒤의 '/' 나 '?' 기호 제거
        route = request.strip('/?')
        
        # -------------------------------------------------------------
        # [처리 1] 사용자가 웹브라우저에 IP 주소만 치고 처음 들어왔을 때 기본 웹페이지 전송
        # -------------------------------------------------------------
        if route == "" or route == "index.html":
            html = webpage()
            client.send('HTTP/1.1 200 OK\nContent-Type: text/html\n\n' + html)
            client.close()
            continue
            
        # -------------------------------------------------------------
        # [처리 2] AJAX 요청 처리 (주소가 api/ 로 시작할 때 브라우저 화면 갱신용 데이터 송수신)
        # -------------------------------------------------------------
        if route.startswith('api/'):
            action = route.replace('api/', '') # "api/btn5" -> "btn5" 형태로 명령어 추출
            
            # 게임이 이미 끝났는데 리셋이 아닌 다른 버튼을 누르면 반응하지 않고 통과
            if is_game_over and action != 'reset':
                pass 
            
            # 숫자 버튼 클릭 처리 ("btn0" ~ "btn9")
            elif action.startswith('btn') and action[3:].isdigit():
                pressed_num = int(action[3:])
                # 현재 커서 위치에 숫자를 할당하고 다음 커서로 이동
                if cursor == 1: n1 = pressed_num; cursor = 2
                elif cursor == 2: n2 = pressed_num; cursor = 3
                elif cursor == 3: n3 = pressed_num; cursor = 4
                elif cursor == 4: n4 = pressed_num; cursor = 5
                    
            # 지우기(erase) 버튼 클릭 처리
            elif action == 'erase':
                # 커서를 한 칸씩 뒤로 밀면서 해당 자리의 숫자를 0으로 초기화
                if cursor == 5: n4 = 0; cursor = 4
                elif cursor == 4: n3 = 0; cursor = 3
                elif cursor == 3: n2 = 0; cursor = 2
                elif cursor == 2: n1 = 0; cursor = 1
                    
            # 제출(submit) 버튼 클릭 처리
            elif action == 'submit':
                user_numbers = [n1, n2, n3, n4]
                
                # 예외 처리: 입력한 4자리에 중복된 숫자가 있는 경우 제출 불가
                if len(set(user_numbers)) < 4:
                    result_text = f"중복된 숫자 조합 {[n1, n2, n3, n4]}는 제출할 수 없습니다!"
                    game_history.insert(1, result_text) # 최신 메시지를 리스트 앞쪽에 삽입
                    n1, n2, n3, n4 = 0, 0, 0, 0        # 입력값 초기화
                    cursor = 1
                else:
                    # 중복이 없으면 판정 함수 호출
                    strike_count, ball_count = check_numbers(n1, n2, n3, n4)
                    
                    if strike_count == 4: # 4 스트라이크면 게임 승리 및 종료
                        result_text = f"[{try_count}] [{n1}{n2}{n3}{n4}] 홈런! 정답입니다!"
                        is_game_over = True
                    else:                 # 맞추지 못했으면 스트라이크/볼 카운트 기록 후 도전 횟수 1 증가
                        result_text = f"[{try_count}] [{n1}{n2}{n3}{n4}] {strike_count} Strike, {ball_count} Ball"
                        try_count += 1 
                    
                    game_history.insert(1, result_text)
                    
                    # 게임이 아직 진행 중이라면 다음 입력을 위해 입력란과 커서 초기화
                    if not is_game_over:
                        n1, n2, n3, n4 = 0, 0, 0, 0
                        cursor = 1
                        
            # 다시 시작(reset) 버튼 클릭 처리
            elif action == 'reset':
                tn1, tn2, tn3, tn4 = random_number() # 새로운 정답 무작위 생성
                print(f"새로운 정답 숫자: {tn1} {tn2} {tn3} {tn4}")
                # 모든 상태 변수 초기화
                n1, n2, n3, n4 = 0, 0, 0, 0
                cursor = 1
                try_count = 1
                is_game_over = False
                game_history = ["새 게임이 시작되었습니다! 숫자를 입력하고 제출을 누르세요."]
            
            # 핵심 AJAX 응답: 변경된 피코의 데이터들을 딕셔너리로 묶음
            response_data = {
                "n1": n1, "n2": n2, "n3": n3, "n4": n4,
                "history": game_history,
                "is_game_over": is_game_over
            }
            # 딕셔너리를 JSON 포맷 문자열로 변환 (예: '{"n1": 1, "n2": 0, ...}')
            json_string = json.dumps(response_data)
            
            # 브라우저에게 JSON 형식 데이터임을 명시(Content-Type)하여 전송 후 소켓 닫기
            client.send('HTTP/1.1 200 OK\nContent-Type: application/json\n\n' + json_string)
            client.close()
            continue

        # 강제 종료 주소('/close') 요청 시 시스템 종료 처리
        if route == 'close':
            sys.exit()
            
        # 매치되는 라우팅이 없을 경우 소켓을 안전하게 닫아줌
        client.close()

# [실행부] 와이파이 연결 -> 소켓 개방 -> 서버 상시 대기 가동
ip = connect()
connection = open_socket(ip)
serve(connection)

