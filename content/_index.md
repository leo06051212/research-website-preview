---
title: ''
summary: 'Academic website of Dr Sean Longyu Ma.'
date: 2026-07-15
type: landing
sections:
  - block: resume-biography-3
    content:
      username: me
      text: ''
      button:
        text: Download CV
        url: uploads/sean-ma-cv.pdf
      headings:
        about: About
        education: Education
        interests: Research Interests
    design:
      background:
        color: '#FBFAF7'
      name:
        size: md
      avatar:
        size: medium
        shape: square
  - block: markdown
    content:
      title: Research Interests
      text: |-
        I design reconfigurable and customised computing systems that translate
        ambitious algorithms into efficient hardware. My current work spans FPGA
        acceleration, RISC-V processor customisation, high-level synthesis, and
        heterogeneous computing.
    design:
      columns: '1'
  - block: collection
    content:
      title: Selected Publications
      filters:
        folders: [publications]
        featured_only: true
    design:
      view: citation
  - block: collection
    content:
      title: Recent Updates
      count: 6
      filters:
        folders: [publications, events, blog]
    design:
      view: card
  - block: markdown
    content:
      title: Prospective Students
      text: |-
        I welcome enquiries from prospective PhD and research master's students
        with strong interests in FPGA/GPU systems, circuits and systems, machine
        learning acceleration, RISC-V, or cross-disciplinary hardware research.
        Please include your CV, academic transcript, and a short description of
        your research interests when contacting me.
    design:
      columns: '1'
---
