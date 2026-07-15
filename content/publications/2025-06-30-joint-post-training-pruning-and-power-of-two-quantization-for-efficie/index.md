---
title: Joint Post-Training Pruning and Power-of-Two Quantization for Efficient Edge
  Computing
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
abstract: Recent advancements in deep neural networks have created significant challenges
  for deploying these models on edge devices due to their computational and memory
  demands. We propose a novel integrated compression framework that combines nonlinear
  orthogonality-based channel pruning with progressive power-of-two (PoT) quantization
  to achieve efficient model compression for edge computing. Our framework first employs
  Radial Basis Function (RBF) kernel-based nonlinear orthogonality measurement to
  identify and remove redundant channels while preserving essential feature representations,
  then applies a layer-wise progressive power-of-two quantization scheme that enables
  efficient hardware implementation through bit-shift operations. Comprehensive experiments
  on CIFAR-10 and ImageNet demonstrate the effectiveness of our approach. On VGG16
  with CIFAR-10, our method achieves 92.36% accuracy while reducing model size by
  98.7% and computational complexity by 98.4%. On ResNet50 with ImageNet, we maintain
  75.01% accuracy while achieving 95.93% model size reduction and 97.24% computational
  complexity reduction. Our framework significantly outperforms existing methods in
  terms of compression ratio and hardware efficiency while maintaining competitive
  accuracy.
summary: ''
featured: false
draft: true
hugoblox:
  ids:
    doi: 10.1109/IJCNN64981.2025.11228510
links:
- type: source
  url: https://ieeexplore.ieee.org/document/11228510
projects: []
slides: ''
citation: Z. Yue, S. L. Ma, C. -W. Sham and C. Fu, "Joint Post-Training Pruning and
  Power-of-Two Quantization for Efficient Edge Computing," 2025 International Joint
  Conference on Neural Networks (IJCNN), Rome, Italy, 2025, pp. 1-8
---
