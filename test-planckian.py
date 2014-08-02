import matplotlib.pyplot as plt

# @returns Planckian locus in xy space from colour temp input in Kelvin
def get_planckian_locus (T):
	x = 0
	y = 0

	# calculations are valid in range 1667 K - 25000 K
	# via: http://en.wikipedia.org/wiki/Planckian_locus#Approximation
	if (T < 4000):
		x =  -266612390.0 / pow(T,3) -  234358.0 / pow(T,2) + 877.6956 / T + 0.179910
	else:
		x = -3025846900.0 / pow(T,3) + 2107037.9 / pow(T,2) + 222.6347 / T + 0.240390

	if (T < 2222):
		y = -1.1063814 * pow(x,3) - 1.34811020 * pow(x,2) + 2.18555832 * x - 0.20219683
	elif (T < 4000):
		y = -0.9549476 * pow(x,3) - 1.37418593 * pow(x,2) + 2.09137015 * x - 0.16748867
	else:
		y =  3.0817580 * pow(x,3) - 5.87338670 * pow(x,2) + 3.75112997 * x - 0.37001483

	return (x, y)

TT = 3500
print get_planckian_locus(TT)

xaxis = []
yaxis = []

for i in range(1500, 6000, 100):
	xc, yc = get_planckian_locus(i)
	xaxis.append(xc)
	yaxis.append(yc)

plt.plot(xaxis, yaxis)
plt.show()
