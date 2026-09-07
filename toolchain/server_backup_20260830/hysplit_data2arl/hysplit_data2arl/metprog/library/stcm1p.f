
      SUBROUTINE STCM1P(STRCMP, X1,Y1, XLAT1,XLONG1,                           &
       XLATG,XLONGG, GRIDSZ, ORIENT)
!*  WRITTEN ON 3/31/94 BY Dr. Albion Taylor  NOAA / OAR / ARL
!------------------------------------------------------------------------------
! PROGRAM HISTORY LOG:
!   LAST REVISED:
!                 31 Mar 1994 (AT)  - initial
!                 20 Oct 2021 (SYZ) - add IMPLICIT NONE and declare all variables
!                 18 Oct 2022 (SYZ) - include/declare subroutine interfaces
      IMPLICIT NONE
      INCLUDE 'cspanf.inc'
      INCLUDE 'cgszll.inc'
      INCLUDE 'cll2xy.inc'
      REAL, PARAMETER :: PI=3.14159265358979,RADPDG=PI/180,DGPRAD=180/PI
      REAL STRCMP(9),X1,Y1,XLAT1,XLONG1,XLATG,XLONGG,GRIDSZ,ORIENT
      integer k
      real    turn,x1a,y1a
      DO K=3,4
        STRCMP (K) = 0.
      ENDDO
        TURN = RADPDG * (ORIENT - STRCMP(1) *                                  &
                  CSPANF(XLONGG - STRCMP(2), -180., 180.) )
      STRCMP (5) = COS (TURN)
      STRCMP (6) = - SIN (TURN)
      STRCMP (7) = 1.
      STRCMP (7) = GRIDSZ * STRCMP(7)                                          &
                   / CGSZLL(STRCMP, XLATG, STRCMP(2))
      CALL CLL2XY (STRCMP, XLAT1,XLONG1, X1A,Y1A)
      STRCMP(3) = STRCMP(3) + X1 - X1A
      STRCMP(4) = STRCMP(4) + Y1 - Y1A
      RETURN
      END SUBROUTINE stcm1p
