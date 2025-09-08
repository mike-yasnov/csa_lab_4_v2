// prob2.alg – Project Euler problem 6: sum square difference

// This program reads an integer n from input and computes
// the difference between (1 + … + n)^2 and (1^2 + … + n^2).

func main() {
    int n;
    int i;
    int sum;
    int sumSquares;
    int result;

    // Prompt the user and read the value of n
    print("Enter n:");
    n = readInt();

    // Initialize accumulators
    sum = 0;
    sumSquares = 0;
    i = 1;

    // Compute sum of integers and sum of squares
    while (i <= n) {
        sum = sum + i;
        sumSquares = sumSquares + i * i;
        i = i + 1;
    }

    // Compute the difference
    result = sum * sum - sumSquares;

    // Output the result
    printInt(result);
}