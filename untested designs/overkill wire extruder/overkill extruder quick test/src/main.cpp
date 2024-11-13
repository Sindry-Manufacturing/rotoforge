#include <Arduino.h>
#include <Servo.h>

const int PULSE = 12;
const int DIR = 13;
const int ENA = 11;
const int DUTY_CYCLE = 50;
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
digitalWrite(ENA, LOW);
Serial.begin(9600);
ESC.attach(7,1000,2000);
//pinMode(7,OUTPUT);
}


void loop() {
//move(100, 3000);
///delay(100);
ESC.write(90);
delay(4000);
ESC.write(180); 
delay(5000);

}