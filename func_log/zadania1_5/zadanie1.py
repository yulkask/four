# нефунциональный 

def reverse_string_imperative(s):
    result = ""
    for i in range(len(s) - 1, -1, -1):
        result += s[i]
    return result

print(reverse_string_imperative("Hello"))  # olleH


#функциональный

def reverse_string_functional(s):
    return "".join(reversed(s))

print(reverse_string_functional("Hello"))  # olleH


