	SUBROUTINE CXY2LL (STCPRM, X,Y, XLAT,XLONG)
!*  WRITTEN ON 3/31/94 BY Dr. Albion Taylor  NOAA / OAR / ARL
!------------------------------------------------------------------------------
! PROGRAM HISTORY LOG:
!   LAST REVISED:
!                 31 Mar 1994 (AT)  - initial
!                 20 Oct 2021 (SYZ) - add IMPLICIT NONE and declare all variables
!                 18 Oct 2022 (SYZ) - include/declare subroutine interfaces
      IMPLICIT NONE
      INCLUDE 'cspanf.inc'
      INCLUDE 'cnxyll.inc'
      REAL, PARAMETER :: REARTH=6371.2
      REAL STCPRM(9),X,Y,XLAT,XLONG
      real eta,eta0,xi,xi0
      XI0 = ( X - STCPRM(3) ) * STCPRM(7) / REARTH
      ETA0 = ( Y - STCPRM(4) ) * STCPRM(7) /REARTH
      XI = XI0 * STCPRM(5) - ETA0 * STCPRM(6)
      ETA = ETA0 * STCPRM(5) + XI0 * STCPRM(6)
      CALL CNXYLL(STCPRM, XI,ETA, XLAT,XLONG)
      XLONG = CSPANF(XLONG, -180., 180.)
      RETURN
      END SUBROUTINE
