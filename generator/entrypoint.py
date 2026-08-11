import os

import log_generator
import loghub_loader

LOG_SOURCE = os.environ.get("LOG_SOURCE", "synthetic")

if __name__ == "__main__":
    if LOG_SOURCE == "loghub":
        loghub_loader.main()
    else:
        log_generator.main()