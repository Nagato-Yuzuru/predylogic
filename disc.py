from functools import reduce

from pydantic import BaseModel

f = reduce(lambda a, b: a | b, [str, int, float])


class F(BaseModel):
    f: f


if __name__ == "__main__":
    print(F(f=1))
    print(F(f="a"))
    print(F(f=[]))
