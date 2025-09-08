// cat.alg – echoes all input characters back to output

func main() {
    char c;
    while (true) {
        // read next character from input
        c = readChar();
        // break if end‑of‑input encountered
        if (c == EOF) {
            break;
        }
        // write the character to output
        printChar(c);
    }
}