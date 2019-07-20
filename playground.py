def func(arg1, arg2, arg3):
    if arg3:
        print(arg1+arg2)
    else:
        print("uh-oh")

state = True
func(1, 2, 3 if state else None)
