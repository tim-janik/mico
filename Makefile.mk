
all:
Q		::= $(if $(findstring 1, $(V)),, @)
QSKIP		::= $(if $(findstring s,$(MAKEFLAGS)),: )
QGEN		  = @$(QSKIP)echo '  GEN     ' $@
QECHO		  = @QECHO() { Q1="$$1"; shift; QR="$$*"; QOUT=$$(printf '  %-8s ' "$$Q1" ; echo "$$QR") && $(QSKIP) echo "$$QOUT"; }; QECHO
ALL_TARGETS	::=
INCLUDES	::= -Imidifile/include/
CCFLAGS		::= -Wall
OPTIMIZE	::= -O3
CFLAGS		 += $(INCLUDES) $(CCFLAGS) $(OPTIMIZE)
CXXFLAGS	 += $(INCLUDES) $(CCFLAGS) $(OPTIMIZE)


# == check-mico-collect ==
check-mico-collect:
	$(QGEN)
	$Q (set -x ; \
		./mico.py --collect . --extension .py | grep 'mico.py' \
	) > $@.log 2>&1 || { echo "$@: error: see $@.log:" >&2; cat $@.log ; false ; }
check: check-mico-collect

# == all ==
all: $(ALL_TARGETS)
