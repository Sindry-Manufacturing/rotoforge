#include <Arduino.h>
const int PULSE = 6;
const int DIR = 7;
const int ENA = 5;
const int DUTY_CYCLE = 50;
const int PERIOD = 1;

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
}

void loop() {
move(1000, 3000);
delay(100);
move(1000, -3000);
delay(100);

}