# Hack your microscope 2026 challenge - Group See

This repository contains all of the resources developed by group See for the HYM challenge 1: Organoid sorting with microfluidics.

The code provides visualization of the image caputred by a XXX camera with simultaneous control of the poseidon syringe pump system. On top of the real-time image we compute a difference image with respect to a reference and then identify flowing particles based on a tunable threshold level. Once the mask is computed the size of the particles is estimated by counting the total masked pixels.

## List of materials

1. Poseidon pump system 
1. Open UC2 

## Setup

**macOS/Linux:**
```sh
./install.sh
source .venv/bin/activate
```

**Windows:**
```bat
install.bat
.venv\Scripts\activate
```

The install scripts will set up a Python 3.11 virtual environment and install all dependencies automatically.

## Run

Make sure the virtual environment is activated (see Setup above) before running. You need to do this each time you open a new terminal. Then run the desired code. 

```sh
python src/pump_gui.py
```



