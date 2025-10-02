#include <stdio.h>

int myvar = 5;
// Dummy-Funktion ohne Rückgabewert und Parameter
void dummy1() {
    printf("dummy1() wurde aufgerufen!\n");
}

int main() {
    printf("Hello World!\n");

    // Aufruf der Dummy-Funktion
    dummy1();

    printf("Der Wert von myvar ist: %d\n", myvar);

    return 0;
}
