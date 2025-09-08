// sort.alg — reads N and N integers from CH and prints them sorted (ascending)

func main() {
    int n;
    int i;
    int j;
    int tmp;
    int swapped;

    print("Enter N:");
    n = readInt();

    // array base at variable a (static memory)
    int a;

    // read array
    i = 0;
    while (i <= n - 1) {
        tmp = readInt();
        set(a, i, tmp);
        i = i + 1;
    }

    // bubble sort
    i = 0;
    while (i <= n - 2) {
        swapped = 0;
        j = 0;
        while (j <= n - 2 - i) {
            // if a[j] > a[j+1] swap
            int aj;
            int aj1;
            aj = get(a, j);
            aj1 = get(a, j+1);
            if (aj <= aj1) {
                // no swap
            }
            else {
                set(a, j, aj1);
                set(a, j+1, aj);
                swapped = 1;
            }
            j = j + 1;
        }
        if (swapped == 0) {
            break;
        }
        i = i + 1;
    }

    // print array
    i = 0;
    while (i <= n - 1) {
        printInt(get(a, i));
        i = i + 1;
    }
}



