
      REAL FUNCTION EQVLAT (XLAT1,XLAT2)
!*  WRITTEN ON 3/31/94 BY Dr. Albion Taylor  NOAA / OAR / ARL
!*  Revised 10/20/21 to add IMPLICIT NONE and declare all variables
      IMPLICIT NONE
      REAL, PARAMETER :: PI=3.14159265358979,RADPDG=PI/180,DGPRAD=180/PI
      REAL XLAT1,XLAT2
      real x,sind
      real al1,al2,sinl1,sinl2,tau
      SIND(X) = SIN (RADPDG*X)
      SINL1 = SIND (XLAT1)
      SINL2 = SIND (XLAT2)
      IF (ABS(SINL1 - SINL2) .GT. .001) THEN
        AL1 = LOG((1. - SINL1)/(1. - SINL2))
        AL2 = LOG((1. + SINL1)/(1. + SINL2))
      ELSE
!  CASE LAT1 NEAR OR EQUAL TO LAT2
        TAU = - (SINL1 - SINL2)/(2. - SINL1 - SINL2)
        TAU = TAU*TAU
        AL1  = 2. / (2. - SINL1 - SINL2) * (1.    + TAU *                      &
                                          (1./3. + TAU *                       &
                                         (1./5. + TAU *                        &
                                         (1./7.))))
        TAU =   (SINL1 - SINL2)/(2. + SINL1 + SINL2)
        TAU = TAU*TAU
        AL2  = -2. / (2. + SINL1 + SINL2) * (1.    + TAU *                     &
                                           (1./3. + TAU *                      &
                                          (1./5. + TAU *                       &
                                          (1./7.))))
      ENDIF
      EQVLAT = ASIN((AL1 + AL2) / (AL1 - AL2))/RADPDG
      RETURN
      END FUNCTION eqvlat
