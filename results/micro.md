| primitive | cycles |
|---|---|
| plain load (hit) | 1.00 |
| cread (hit) | 2.02 |
| cread + CAFAIL check (csrr, andi) | 7.03 |
| csrr 0xCC0 alone | 1.03 |
| untagOne | 0.00 |
| untagAll | 3.99 |
| plain store | 1.00 |
| cread + cwrite (try-lock pattern) | 17.04 |
| amoswap.w (in-L1 AMO) | 14.01 |
| lr.w + sc.w | 24.04 |
| fence rw,rw | 6.02 |
