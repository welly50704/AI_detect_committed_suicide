import cv2, time
# importing datetime class from datetime library 
from datetime import datetime 
from time import sleep
import boto3
import csv
#匯入我們整理過的Facedetails
from Recognition import FaceDetails
# convert text to speech
import pyttsx3
#為了寄送email
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
from email.mime.image import MIMEImage
from pathlib import Path

import threading

def login_aws(key_url):
    with open(key_url,'r') as input:
        reader = csv.reader(input)
        for line in reader:
            access_key_id = line[2]
            secret_access_key = line[3]
    # rekognition
    client = boto3.client('rekognition',
                        aws_access_key_id=access_key_id,
                        aws_secret_access_key=secret_access_key,
                        region_name='us-west-2')
    return client

def emotion_and_count(emotion, count):
    global rlock
    rlock.acquire()
    try:
        if (emotion == 'SAD' or emotion == 'FEAR') and count == 1:
            print('有人需要幫忙!')

            t2.start()
            
            for i in range(2):
                engine.say("有人可能想不開!")
            engine.runAndWait()
        else:
            print(f'情緒:{emotion};共有{count}人\n沒事啦!想太多\n')
            mode =0
            con = 0 
    
    finally:
        rlock.release()

def send_gmail(imgfilename):

    content = MIMEMultipart()  # 建立MIMEMultipart物件
    content["subject"] = "注意!有疑似想自殺的人!"  # 郵件標題
    content["from"] = "Sender"  # 寄件者
    content["to"] = "Receiver" # 收件者
    content.attach(MIMEText("Demo python send email"))  # 郵件內容
    content.attach(MIMEImage(Path(imgfilename).read_bytes()))  # 郵件圖片內容

    with smtplib.SMTP(host="smtp.gmail.com", port="587") as smtp:  # 設定SMTP伺服器
        try:
            smtp.ehlo()  # 驗證SMTP伺服器
            smtp.starttls()  # 建立加密傳輸
            smtp.login("Your gmail", "Your pplication password")  # 登入寄件者gmail
            smtp.send_message(content)  # 寄送郵件
            print("Complete!")
        except Exception as e:
            print("Error message: ", e)

# 接收攝影機串流影像，用多線程的方式降低緩衝區堆疊圖幀的問題，以解決opencv卡礑的困。
# Using threading to sloved opencv(cv2)'s buffer size problem(frame lag),this can reduce the problem of frames stack.
class Cam_capture:
    def __init__(self, URL):
        self.Frame = []
        self.status = False
        self.isstop = False
		
	# Connecting the camera。
        self.capture = cv2.VideoCapture(URL)

    def start(self):
	# 把程式放進子執行緒，daemon=True 表示該執行緒會隨著主執行緒關閉而關閉。
        print('cam started!')
        threading.Thread(target=self.queryframe, daemon=True, args=()).start()

    def stop(self):
	# 記得要設計停止無限迴圈的開關。
        self.isstop = True
        print('cam stopped!')
   
    def getframe(self):
	# 當有需要影像時，再回傳最新的影像。
        return self.Frame
        
    def queryframe(self):
        while (not self.isstop):
            self.status, self.Frame = self.capture.read()
        
        self.capture.release()



def main():
    # 1. 建立連接AWS的client
    key_url = "輸入aws金鑰檔案位置"
    client = login_aws(key_url)

    '''
    pyttsx通過初始化來獲取語音引擎。當我們第一次呼叫init操作的時候，
    會返回一個pyttsx的engine物件，再次呼叫的時候，如果存在engine物件例項，
    就會使用現有的，否則再重新建立一個

    '''
    engine = pyttsx3.init()
    voices = engine.getProperty('voices')
    # index為設定音色種類，有0, 1可選
    engine.setProperty('voice', voices[0].id)
    engine.setProperty('rate', 150)

    con = 0 
    # Assigning our static_back to None 
    static_back = None

    # 連接攝影機
    # Capturing video 
    video = Cam_capture(0)
    video.start()
    count = 0
    # 啟動子執行緒

    # 暫停1秒，確保影像已經填充
    time.sleep(1)
    emotion = []
    count = 0
    rlock = threading.RLock()
    t1=threading.Thread(target=emotion_and_count, args=(emotion, count))


    while True: 
        # Reading frame(image) from video 
        frame = video.getframe()
    
        # Converting color image to gray_scale image 
        # 轉成灰階影像
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) 
    
        # Converting gray scale image to GaussianBlur  
        # so that change can be find easily 
        gray = cv2.GaussianBlur(gray, (21, 21), 0) 
    
        # In first iteration we assign the value  
        # of static_back to our first frame (最初static_back的值會是None,因此會賦值給static_back)
        if static_back is None: 
            static_back = gray 
            continue
    
        # Difference between static background  
        # and current frame(which is GaussianBlur)(比對靜態背景和目前畫面的差異) 
        diff_frame = cv2.absdiff(static_back, gray) 
    
        # If change in between static background and 
        # current frame is greater than 150 it will show white color(255) 
        # (第三個參數:0為最黑,255為最白，高於閥值的話會將其像素值賦予你第三個參數的值)
        # 
        thresh_frame = cv2.threshold(diff_frame, 150, 255, cv2.THRESH_BINARY)[1] 
        # 影像膨脹
        thresh_frame = cv2.dilate(thresh_frame, None, iterations = 2) 
    
        # Finding contour of moving object 
        # contours(cnts)：輸出的 contours，每一個 contour 都是 Point 形成的集合
        # hierarchy：輸出 contours 之間的樹狀結構關係，每一個元素都是以 [next, prev, firstChild, parent] 表示
        cnts,hierarchy = cv2.findContours(thresh_frame.copy(),  
                        cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE) 
        # 改變的範圍
        for contour in cnts: 
            if cv2.contourArea(contour) < 7000: 
                continue
    
            (x, y, w, h) = cv2.boundingRect(contour) 
            # making green rectangle arround the moving object 
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 3) 
    
    
        if(thresh_frame.sum()>100):
            #print(thresh.sum(),con)
            con+=1
        else:
            if(con>0):
                con-=1
                #print("subs")
        cv2.imshow('current',thresh_frame)
        
        # Displaying image in gray_scale 
        ###cv2.imshow("Gray Frame", gray) 
    
        # Displaying the difference in currentframe to 
        # the staticframe(very first_frame) 
        ###cv2.imshow("Difference Frame", gray) 
    
        # Displaying the black and white image in which if 
        # intensity difference greater than 30 it will appear white 
        ###cv2.imshow("Threshold Frame", thresh_frame) 
    
        # Displaying color frame with contour of motion of object 
        #偵測移動物並拍照

        if con>20:
            nowtime = round(time.time())
            str_nowtime = str(round(time.time()))
            imgfilename = 'D:/cv2photo/' + str_nowtime + '.jpg'

            try:
                cv2.imwrite(imgfilename, frame)
                print(nowtime)
                connect_FD = FaceDetails(client, imgfilename)
                emotion = connect_FD.emotion()
                count = connect_FD.count_face()
                t1=threading.Thread(target=emotion_and_count, args=(emotion, count))
                t2 = threading.Thread(target=send_gmail, args=(imgfilename,))
                t1.start()
            except FileNotFoundError:
                print('沒有找到檔案')
            con = 0
            
            
        cv2.imshow("Color Frame", frame) 
    
        key = cv2.waitKey(100) 
        # if q entered whole process will stop 
        if key == ord('q'): 
            video.capture.release() 
            break

    video.capture.release() 
    
    # Destroying all the windows 
    cv2.destroyAllWindows() 

if __name__ == '__main__':
    main()