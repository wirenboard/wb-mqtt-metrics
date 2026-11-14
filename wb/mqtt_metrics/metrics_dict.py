from .metrics import Data, DevRoot, FreeRam, LoadAverage, SdCard

METRICS = {"LoadAverage": LoadAverage, "FreeRam": FreeRam, "DevRoot": DevRoot, "Data": Data, "SdCard": SdCard}
