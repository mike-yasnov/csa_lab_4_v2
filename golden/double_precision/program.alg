// double_precision.alg – demonstrates 64‑bit arithmetic

// This program reads two 64‑bit integers from the input, adds them and
// prints the 64‑bit sum.

func main() {
    long a;
    long b;
    long sum;

    // Read the first 64‑bit integer
    print("Enter the first 64-bit integer:");
    a = readLong();

    // Read the second 64‑bit integer
    print("Enter the second 64-bit integer:");
    b = readLong();

    // Compute the sum
    sum = a + b;

    // Output the result
    printLong(sum);
}