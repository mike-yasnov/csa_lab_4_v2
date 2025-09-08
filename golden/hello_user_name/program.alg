// hello_user_name.alg – asks the user for their name and greets them

func main() {
    string name;
    // Ask the user for their name
    print("What is your name?");
    // Read a line from the input (until newline)
    name = readString();
    // Greet the user with their name
    print("Hello, ");
    print(name);
    print("!");
}