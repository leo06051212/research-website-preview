---
title: 'PQDE: Comprehensive Progressive Quantization with Discretization Error for
  Ultra-Low Bitrate MobileNet towards Low-Resolution Imagery'
authors:
- Zongcheng Yue
- Ran Wu
- me
- Chong Fu
- Chiu-Wing Sham
date: '2024-04-22T00:00:00Z'
publication_types:
- paper-conference
publication:
  name: 2024 IEEE 6th International Conference on AI Circuits and Systems (AICAS)
abstract: In deep learning, quantization is employed to tackle deployment challenges
  of neural networks in resource-limited environments like mobile and edge devices.
  Traditional full-precision (32-bit floating-point) models, while effective, are
  restricted by their high memory and computational demands, limiting their use in
  devices with constrained computational power and resources. To address this problem,
  we present a neural network quantization methodology that is primarily geared to-wards
  resource-constrained devices and inputs. Our methodology focuses on optimizing network
  performance for resource-limited settings, featuring a unique forward quantization
  function. This function employs the Minimize Discretization Error (MDE) technique
  to reduce information loss during quantization, particularly targeting near-zero
  weights, while maintaining computational efficiency and model accuracy. Additionally,
  we integrate the Arctangent Soft Round (ASR) method in the forward process to further
  smooth the data in low-bit quantization scenarios. Finally, we design a progressive
  quantization method, progressively transitioning from full precision to low bits,
  stabilizing the network at each quantization level. Tested on a resource-efficient
  variant of MobileNetV2 and low-resolution input data (CIFAR10/100), our method surpasses
  most contemporary techniques in terms of lightweight model performance. Through
  progressive quantization, our 4-bit quantized model even exceeds the accuracy of
  its full-precision counterpart as evidenced by our ablation studies.
summary: ''
featured: false
draft: true
cv_provenance: migrated_legacy
hugoblox:
  ids:
    doi: 10.1109/AICAS59952.2024.10595949
links:
- type: source
  url: https://ieeexplore.ieee.org/abstract/document/10595949/
projects: []
slides: ''
citation: 'Z. Yue, R. Wu, L. Ma, C. Fu and C. -W. Sham, "PQDE: Comprehensive Progressive
  Quantization with Discretization Error for Ultra-Low Bitrate MobileNet towards Low-Resolution
  Imagery," 2024 IEEE 6th International Conference on AI Circuits and Systems (AICAS),
  Abu Dhabi, United Arab Emirates, 2024'
---
