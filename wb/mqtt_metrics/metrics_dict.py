from .metrics import Data, DevRoot, FreeRam, LoadAverage

METRICS = {"LoadAverage": LoadAverage, "FreeRam": FreeRam, "DevRoot": DevRoot, "Data": Data}
