#------------------------------------------------------------------
# Makefile for the ARL packing library   r 
#------------------------------------------------------------------

include ../../Makefile.inc

SHELL = /bin/sh

LIB=libhysplit.a

#SUN5 = -O -free
#AIXC = -O3 
#AIX8 = -O3 -qarch=auto -qmaxmem=8192 -qstrict
#AIX6 = -O -qarch=com -qmaxmem=8192
#AIX5 = -O -qarch=com -qmaxmem=8192
#AIX4 = -O -qarch=pwr2 -qmaxmem=8192
#AIX3 = -O -qcharlen=3072 -Pv -Wp,-gv
#DEC3 = -O -assume byterecl
#SGI5 = -O -bytereclen -freeform
#SGI3 = -O -old_rl
#ABSF = -O1 -f free 
#PGF9 = -O -Mfree -byteswapio
#INTL = -O -FR -assume byterecl -convert big_endian -I.
#GF95 = -O2 -fendian=big -ffree-form 
#GFOR = -O2 -fconvert=big-endian -frecord-marker=4 -ffree-form 
#CFOR = -fconvert=big-endian -frecord-marker=4 -ffree-form -Wall -fbounds-check -fbacktrace -finit-local-zero

#CFLAGS = $(GFOR)
LFLAGS = -vr
#FC = gfortran

CODE =          \
       pakini.f \
       pakinp.f \
       pakndx.f \
       pakout.f \
       pakrec.f \
       pakset.f \
       tm2day.f \
       tm2jul.f \
       tm2min.f \
       tminit.f \
       tmplus.f \
       w3code.f \
       cc2gll.f \
       cc2gxy.f \
       ccrvll.f \
       ccrvxy.f \
       cg2cll.f \
       cg2cxy.f \
       cg2wll.f \
       cg2wxy.f \
       cgszll.f \
       cgszxy.f \
       cll2xy.f \
       cnllxy.f \
       cnxyll.f \
       cpolll.f \
       cpolxy.f \
       cspanf.f \
       cw2gll.f \
       cw2gxy.f \
       cxy2ll.f \
       eqvlat.f \
       stcm1p.f \
       stcm2p.f \
       stlmbr.f \
       fcclos.f \
       fcgtps.f \
       fcopen.f \
       fcptpd.f \
       fcptps.f \
       fcread.f

$(LIB) : $(CODE)
	for member in $?; do make member MODULE=$$member;done

member : $(MODULE)
	$(FC) -c $(FFLAGS_FREEFORM) $(FFLAGS) $?                                 
	$(AR) $(LFLAGS) $(LIB) $(?F:.f=.o)
	ranlib $(LIB)
	rm -f $(?F:.f=.o)

clean :
	rm -f $(LIB)
	rm -f *.mod
