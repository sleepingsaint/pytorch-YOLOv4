# Conversion of Yolo to ONNX and Inference



## 1. Conversion
___
## Darknet2ONNX

- **This script is to convert the official pretrained darknet model into ONNX**

- **Pytorch version Recommended:**

    - Pytorch 1.4.0 for TensorRT 7.0 and higher
    - Pytorch 1.5.0 and 1.6.0 for TensorRT 7.1.2 and higher

- **Install onnxruntime**

    ```sh
    pip install onnxruntime-gpu
    ```

- **Run python script to generate ONNX model and run the demo**

    ```sh
    python darknet2onnx.py -c <cfgFile> -w <weightFile> -i <imageFile> -b <batchSize> -n <num classes>
    ```

## Dynamic or static batch size

- **Positive batch size will generate ONNX model of static batch size, otherwise, batch size will be dynamic**
    - Dynamic batch size will generate only one ONNX model
    - Static batch size will generate 2 ONNX models, one is for running the demo (batch_size=1)


## 2. Inference
___

This script is run use the onnxruntime to run inference on a video

```sh
python test_onnx.py -m <path to the onnx model> -i <path to the input video file> -o <path to the output video file> -f <specify number of frames to run inference on> -c <num classes> -v <vebose flag>
```

