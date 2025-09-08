// cat_trap.alg — echo via CH interrupt (irq1)

func irq1() {
    char c;
    c = readChar();
    if (c == 0) {
        // no data
    }
    else {
        printChar(c);
    }
}

func main() {
    // enable interrupts and idle forever
    ei();
    while (true) {
    }
}


