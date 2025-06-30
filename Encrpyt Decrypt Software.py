def caesar_cipher(text, shift):
    result = []
    for char in text:
        if char.isupper():
            base = ord('A')
            shifted = (ord(char) - base + shift) % 26
            result.append(chr(base + shifted))
        elif char.islower():
            base = ord('a')
            shifted = (ord(char) - base + shift) % 26
            result.append(chr(base + shifted))
        else:
            result.append(char)
    return ''.join(result)

def main():
    print("Caesar Cipher Program")
    while True:
        mode = input("\nDo you want to (e)ncrypt or (d)ecrypt? (q to quit) ").strip().lower()
        
        if mode == 'q':
            print("Exiting program. Goodbye!")
            break
            
        if mode not in ['e', 'd', 'encrypt', 'decrypt']:
            print("Invalid mode. Please choose 'e', 'd', or 'q' to quit.")
            continue
            
        message = input("Enter the message: ")
        shift = int(input("Enter the shift value: "))
        
        if mode == 'e' or mode == 'encrypt':
            result = caesar_cipher(message, shift)
            print("Encrypted message:", result)
        elif mode == 'd' or mode == 'decrypt':
            result = caesar_cipher(message, -shift)
            print("Decrypted message:", result)
            
        again = input("\nPerform another operation? (y/n) ").strip().lower()
        if again != 'y':
            print("Exiting program. Goodbye!")
            break

if __name__ == "__main__":
    main()