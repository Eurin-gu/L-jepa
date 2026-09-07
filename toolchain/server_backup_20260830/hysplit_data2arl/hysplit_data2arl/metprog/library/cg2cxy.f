	SUBROUTINE CG2CXY (STCPRM, X,Y, UG,VG, UE,VN)
!*  WRITTEN ON 3/31/94 BY Dr. Albion Taylor  NOAA / OAR / ARL
!------------------------------------------------------------------------------
! PROGRAM HISTORY LOG:
!   LAST REVISED:
!                 31 Mar 1994 (AT)  - initial
!                 20 Oct 2021 (SYZ) - add IMPLICIT NONE and declare all variables
!                 18 Oct 2022 (SYZ) - include/declare subroutine interfaces
      IMPLICIT NONE
      INCLUDE 'cxy2ll.inc'
      INCLUDE 'cg2cll.inc'
      REAL, PARAMETER :: REARTH=6371.2
      REAL STCPRM(9),X,Y,UG,VG,UE,VN
      DOUBLE PRECISION XPOLG,YPOLG,TEMP,XI0,ETA0
      REAL, PARAMETER :: PI=3.14159265358979,RADPDG=PI/180,DGPRAD=180/PI
      real xlat,xlong
      XI0 = ( X - STCPRM(3) ) * STCPRM(7) / REARTH
      ETA0 = ( Y - STCPRM(4) ) * STCPRM(7) /REARTH
      XPOLG = STCPRM(6) - STCPRM(1) * XI0
      YPOLG = STCPRM(5) - STCPRM(1) * ETA0
      TEMP = SQRT ( XPOLG ** 2 + YPOLG ** 2 )
!* Revised 2/12/02 to allow cartographic wind vector transformations everywhere
!* except at the poles, with WMO conventions only at the poles.
      IF (TEMP .LE. 1.e-3) THEN
!* Close to either pole, revert to Lat-Long system to ensure compatibility
!* with CXY2LL usage
        CALL CXY2LL(STCPRM, X,Y, XLAT,XLONG)
        CALL CG2CLL(STCPRM, XLAT,XLONG, UG,VG, UE,VN)
      ELSE
!* Elsewhere, use vector algebra instead of time consuming trigonometry.
        XPOLG = XPOLG / TEMP
        YPOLG = YPOLG / TEMP
!*  CHANGE MADE 3/9/99 TO ALLOW UG,VG TO HAVE SAME STORAGE AS UE,VN
        TEMP = YPOLG * UG - XPOLG * VG
        VN = YPOLG * VG + XPOLG * UG
        UE = TEMP
!* PERMITTING ROTATE OF WINDS IN PLACE
      ENDIF
      RETURN
      END SUBROUTINE
