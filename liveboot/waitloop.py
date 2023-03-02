import time

class WaitLoop:
    """
    use as a context manager only; ex:

    try:
        with WaitLoop(60) as waitloop:
            while True:
                if the_right_thing():
                    break
                waitloop.tick()
    except TimeoutError:
        print("the right thing did not happen within 60 s")
    """

    def __init__(self, timeout=60, period=1):
        self.period = period
        self.timeout = timeout

    def __enter__(self):
        self.begin = time.time()
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        pass

    def tick(self):
        if time.time() - self.begin >= self.timeout:
            raise TimeoutError(f"waiting each {self.period} s "
                               f"for {self.timeout} s has reached timeout")
        time.sleep(self.period)