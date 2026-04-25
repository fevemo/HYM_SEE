# Hack your microscope 2026 challenge - Group See

This repository contains all of the resources developed by group See for the HYM challenge 1: Organoid sorting with microfluidics.

The code provides visualization of the image caputred by a Hikrobotics camera with simultaneous control of the poseidon syringe pump system. On top of the real-time image we compute a difference image with respect to a reference and then identify flowing particles based on a tunable threshold level. Once the mask is computed the size of the particles is estimated by counting the total masked pixels.

## List of materials

1. [Poseidon pump system](https://github.com/pachterlab/poseidon)
1. [OpenUC2 Corebox](https://openuc2.com/product-overview-2/)
1. [Hikrobotics mv-cs060-10um-pro](https://www.hikrobotics.com/en/machinevision/productdetail/?id=5715)
1. 3x 1ml BD plastic syringe (18mm2)
1. [2m of Tygon tube ND-100-80 (ID: 0.04 in, OD: 0.07 in)](https://darwin-microfluidics.com/products/tygon-nd-100-80-micro-tubing)
1. [3 Tube Tuck Luer Connector for 1/16 tubing (1 pack)](https://www.microfluidic-chipshop.com/connectors/1243-2683-tube-tuck-mini-luer-connector-for-116-tubing-fluidic-1581.html#/20-material-tpe/26-color-blue)
1. XY stage with M6 holes
1. Custom open UC2 adapter plate for



## Optics
The microscope was build using the [OpenUC2 Corebox](https://openuc2.com/product-overview-2/). Documentation about the corebox can be found [here](https://docs.openuc2.com/usage/disc/corebox/en/core_intro/). The optical setup was adapted to be able to fit on a Melles Griot Stage for XY translation while fixing the sample with a Thorlabs post holder. 

![HYM_SEE_Setup](Illustrations/HYC_TEAMSEE_Setup.jpeg)

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



