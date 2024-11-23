#include <Arduino.h>
#include <Servo.h>

const int PULSE = 12;
const int DIR = 13;
const int ENA = 11;
const int DUTY_CYCLE = 50;
const int POTPIN = 0;
const int BUTTONPIN = 1;
const int STEPPERPOT = 2;

int stepspeed;
int speed = 0;
Servo ESC;


void move(unsigned int speed, int distance){
  /*speed is given in steps/sec, distance is given in steps*/
  int period = 1000 / speed;

  if (distance > 0)
  {
    digitalWrite(DIR, HIGH);
  }else{
    digitalWrite(DIR, LOW);
    distance = -1 * distance;
  } 

  for (int i = 0; i < distance; i++)
  {
    delay(period);
    digitalWrite(PULSE, HIGH);
    delay(period);
    digitalWrite(PULSE, LOW);
  }
}

void setup() {
pinMode(PULSE, OUTPUT);
pinMode(DIR, OUTPUT);
pinMode(ENA, OUTPUT);
pinMode(POTPIN,INPUT);
pinMode(BUTTONPIN, INPUT);
pinMode(STEPPERPOT ,INPUT);
digitalWrite(ENA, LOW);

Serial.begin(9600);
ESC.attach(7,1000,2000);


}


void loop() {
speed = analogRead(POTPIN);
speed = map(speed, 0, 1023, 0, 180);
ESC.write(speed);
Serial.print("ervoSpeed:");
Serial.println(speed);

stepspeed = analogRead(STEPPERPOT);
Serial.print("stepspeed");
Serial.println(stepspeed);

if(analogRead(BUTTONPIN) > 1022){
move(stepspeed, 500);
}


}