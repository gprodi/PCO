#pragma once
#include <WiFi.h>  // même API minimale que WiFi.h pour le test de syntaxe
void configTime(const char* tz, const char* s1, const char* s2 = nullptr, const char* s3 = nullptr);
