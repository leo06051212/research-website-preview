---
title: Adaptive Gradual Quantization with a Custom RISC-V SIMD Accelerator
authors:
- Zongcheng Yue
- Dongwei Yan
- me
- Chiu-Wing Sham
date: '2025-12-15T00:00:00Z'
publication_types:
- paper-conference
publication:
  name: 2025 IEEE 18th International Symposium on Embedded Multicore/Many-core Systems-on-Chip
    (MCSoC)
abstract: 'Neural network quantization is essential for deploying deep learning models
  on resource-constrained devices, but it presents a critical trade-off: aggressive,
  low-bit quantization often decimates model accuracy, while standard processors fail
  to efficiently execute the resulting operations. In this paper, we propose a full-stack,
  algorithm-hardware co-design that resolves this conflict. Our adaptive gradual quantization
  algorithm incrementally reduces precision in stages, a method that ensures training
  stability and preserves high accuracy at 4-bit precision, avoiding the catastrophic
  performance drop common in direct quantization. To translate this model compactness
  into execution speed, we introduce a custom sub-word SIMD instruction for the RISC-V
  architecture that dramatically accelerates 4-bit computations. Experiments on CIFAR-10
  and Tiny-ImageNet confirm our method achieves state-of-the-art accuracy, while simulations
  validate a significant inference speedup of over 8x, proving our synergistic approach
  delivers both high performance and efficiency.'
summary: ''
featured: false
draft: true
cv_provenance: migrated_legacy
hugoblox:
  ids:
    doi: 10.1109/MCSoC67473.2025.00122
links:
- type: source
  url: https://ieeexplore.ieee.org/document/11310955
projects: []
slides: ''
citation: Z. Yue, D. Yan, S. L. Ma and C. -W. Sham, "Adaptive Gradual Quantization
  with a Custom RISC-V SIMD Accelerator," 2025 IEEE 18th International Symposium on
  Embedded Multicore/Many-core Systems-on-Chip (MCSoC), Singapore, Singapore, 2025,
  pp. 768-771.
---
