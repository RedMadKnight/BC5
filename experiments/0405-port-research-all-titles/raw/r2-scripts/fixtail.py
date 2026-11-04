import sys
p = sys.argv[1]
s = open(p, encoding='utf-8').read()
reps = [
 ("| - | KL25 | Trinity / Pro mode |", "| 235 | KL25 | Trinity / Pro mode |"),
 ("| - | KS45 | Psml PSSR |", "| 237 | KS45 | Psml PSSR |"),
 ("| - | KS47 | Error and Signin dialog overlay | - |", "| 238 | KS47 | Error and Signin dialog overlay | - |"),
 ("| - | KA49 (+KS48) | DualSense Bluetooth", "| 236 | KA49 (+KS48) | DualSense Bluetooth"),
 ("| - | KS49 | PSVR2 controllers | - |", "| 239 | KS49 | PSVR2 controllers | - |"),
 ("| - | KK41 | ZArchive read-only mounts | - |", "| 233 | KK41 | ZArchive read-only mounts | - |"),
 ("| KK27 | e4-now | `sceKernelGetAvailableCpumask`", "| KK27 | 55 | `sceKernelGetAvailableCpumask`"),
 ("| - | - | The FreeBSD `_umtx_op` op numbers |", "| KK24 (+SK16) | 43 | The FreeBSD `_umtx_op` op numbers |"),
 ("| KS11 | - | Psml NOT_TRINITY_MODE", "| KS11 | 93 | Psml NOT_TRINITY_MODE"),
 ("| KA22 | - | AudioIn param enum |", "| KA22 | 164 | AudioIn param enum |"),
 ("| KA20 | - | 8-channel order |", "| KA20 | 163 | 8-channel order |"),
 ("| KA19 | - | KytyPS5's ContextResetParam defaults |", "| KA19 | 202 | KytyPS5's ContextResetParam defaults |"),
]
for a, b in reps:
    assert a in s, a
    s = s.replace(a, b)
open(p, 'w', encoding='utf-8').write(s)
print('ok')
