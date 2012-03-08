all: \
	$(patsubst %.dot,%.png,$(wildcard *.dot)) \
	$(patsubst %.dot,%.xdot,$(wildcard *.dot))

%.png: %.dot
	dot -Tpng -o$@ $<

%.xdot: %.dot
	dot -Txdot -o$@ $<
