---
title: 'LHA: Layer-wise Hardware Acceleration of Progressive Quantizing Inference
  through Partial Reconfiguration for Edge Computing'
authors:
- Zongcheng Yue
- me
- Chiu-Wing Sham
- Chong Fu
date: '2025-06-30T00:00:00Z'
publication_types:
- paper-conference
publication:
  name: 2025 International Joint Conference on Neural Networks (IJCNN)
abstract: As the need for real-time, low-power deep learning at the edge increases,
  efficient hardware acceleration becomes crucial. Traditional edge hardware designs
  often scale to accommodate neural network sizes, which can degrade overall performance
  by taxing the hardware. To solve this, we propose a novel Layer-wise Hardware Acceleration
  (LHA) approach for Deep Neural Network (DNN) inference, leveraging progressive quantization
  and Partial Reconfiguration (PR). We first apply progressive quantization to systematically
  reduce the bit-width of network weights and activations, lowering computational
  and memory demands. Then, we utilize Field Programmable Gate Arrays (FPGAs) with
  PR capabilities to dynamically reconfigure hardware for each quantized network layer
  in sequence. This method optimizes FPGA resource usage, tailors to each layer’s
  needs, and reallocates freed resources to boost overall performance. Experiments
  show that LHA significantly enhances resource efficiency while maintaining inference
  performance on edge devices.
summary: ''
featured: true
draft: false
cv_provenance: migrated_legacy
hugoblox:
  ids:
    doi: 10.1109/IJCNN64981.2025.11229400
links:
- type: source
  url: https://ieeexplore.ieee.org/document/11229400
projects: []
slides: ''
citation: 'Z. Yue, S. L. Ma, C. -W. Sham and C. Fu, "LHA: Layer-wise Hardware Acceleration
  of Progressive Quantizing Inference through Partial Reconfiguration for Edge Computing,"
  2025 International Joint Conference on Neural Networks (IJCNN), Rome, Italy, 2025,
  pp. 1-8'
---
