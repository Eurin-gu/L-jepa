	SUBROUTINE CLL2XY (STCPRM, XLAT,XLONG, X,Y)
!*  WRITTEN ON 3/31/94 BY Dr. Albion Taylor  NOAA / OAR / ARL
!------------------------------------------------------------------------------
! PROGRAM HISTORY LOG:
!   LAST REVISED:
!                 31 Mar 1994 (AT)  - initial
!                 20 Oct 2021 (SYZ) - add IMPLICIT NONE and declare all variables
!                 18 Oct 2022 (SYZ) - include/declare subroutine interfaces
      IMPLICIT NONE
      INCLUDE 'cnllxy.inc'
      REAL, PARAMETER :: REARTH=6371.2
      REAL STCPRM(9),XLAT,XLONG,X,Y
      real eta,xi
      CALL CNLLXY(STCPRM, XLAT,XLONG, XI,ETA)
      X = STCPRM(3) + REARTH/STCPRM(7) *                                       &
                   (XI * STCPRM(5) + ETA * STCPRM(6) )
      Y = STCPRM(4) + REARTH/STCPRM(7) *                                       &
                   (ETA * STCPRM(5) - XI * STCPRM(6) )
      RETURN
      END SUBROUTINE cll2xy
