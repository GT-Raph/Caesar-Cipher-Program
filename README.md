# Caesar Cipher Program

## Overview
This program implements the Caesar cipher, a classic encryption technique that shifts letters in the alphabet by a specified number of positions. It allows users to either encrypt or decrypt messages using this method.

## Features
- **Encryption**: Shifts letters forward in the alphabet by a user-specified shift value
- **Decryption**: Shifts letters backward in the alphabet by the same shift value
- **Case Preservation**: Maintains original letter cases (uppercase/lowercase)
- **Non-alphabetic Handling**: Leaves non-alphabetic characters unchanged
- **Interactive Menu**: Simple text-based interface for easy operation

## How to Use
1. Run the program (`python caesar_cipher.py`)
2. Choose an operation:
   - `e` or `encrypt` to encrypt a message
   - `d` or `decrypt` to decrypt a message
   - `q` to quit the program
3. Enter your message when prompted
4. Enter the shift value (an integer)
5. View the result
6. Choose to perform another operation or quit

## Technical Details
- The cipher wraps around the alphabet (Z shifts to A with shift=1)
- Only alphabetic characters are modified; numbers, symbols, and spaces remain unchanged
- The program handles both uppercase and lowercase letters appropriately

## Example Usage
```
Caesar Cipher Program

Do you want to (e)ncrypt or (d)ecrypt? (q to quit) e
Enter the message: Hello World!
Enter the shift value: 3
Encrypted message: Khoor Zruog!

Perform another operation? (y/n) y

Do you want to (e)ncrypt or (d)ecrypt? (q to quit) d
Enter the message: Khoor Zruog!
Enter the shift value: 3
Decrypted message: Hello World!
```

## Requirements
- Python 3.x

## Limitations
- Only works with English alphabet characters
- No protection against very large shift values (though they are effectively reduced modulo 26)
- Basic implementation without advanced security features

This program is for educational purposes and should not be used for secure communications.
