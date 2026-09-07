
      SUBROUTINE CNLLXY (STRCMP, XLAT,XLONG, XI,ETA)
!*  WRITTEN ON 3/31/94 BY Dr. Albion Taylor  NOAA / OAR / ARL
!*  CHANGES FOR NEAR-POLE LOCATIONS ON 10/1/21 BY Dr. Sonny Zinn
!*  Revised on 10/20/21 to add IMPLICIT NONE and to declare all variables
!*  Revised on 1/3/25 to avoid errors when XLAT=90.0 or -90.0
!  MAIN TRANSFORMATION ROUTINE FROM LATITUDE-LONGITUDE TO
!  CANONICAL (EQUATOR-CENTERED, RADIAN UNIT) COORDINATES
      IMPLICIT NONE
      INCLUDE 'cspanf.inc'
      REAL, PARAMETER :: PI=3.14159265358979,RADPDG=PI/180,DGPRAD=180/PI
      REAL, PARAMETER :: LATLMT=89.7438       ! FROM ASIN(0.99999)
      REAL STRCMP(9),XLAT,XLONG,XI,ETA
      DOUBLE PRECISION GAMMA
      DOUBLE PRECISION DLONG,DLAT,SLAT,MERCY,GMERCY
      REAL DELTA, EPS
      REAL CSDGAM,GDLONG,RHOG1,SNDGAM
      GAMMA = STRCMP(1)
      DLAT = XLAT
      DLONG = CSPANF(XLONG - STRCMP(2), -180., 180.)
      DLONG = DLONG * RADPDG
      GDLONG = GAMMA * DLONG
      IF (ABS(GDLONG) .LT. .01) THEN
!  CODE FOR GAMMA SMALL OR ZERO.  THIS AVOIDS ROUND-OFF ERROR OR DIVIDE-
!  BY ZERO IN THE CASE OF MERCATOR OR NEAR-MERCATOR PROJECTIONS.
        GDLONG = GDLONG * GDLONG
        SNDGAM = DLONG * (1. - 1./6. * GDLONG *                                &
                           (1. - 1./20. * GDLONG *                             &
                           (1. - 1./42. * GDLONG )))
        CSDGAM = DLONG * DLONG * .5 *                                          &
                           (1. - 1./12. * GDLONG *                             &
                           (1. - 1./30. * GDLONG *                             &
                           (1. - 1./56. * GDLONG )))
      ELSE
! CODE FOR MODERATE VALUES OF GAMMA
        SNDGAM = SIN (GDLONG) /GAMMA
        CSDGAM = (1. - COS(GDLONG) )/GAMMA /GAMMA
      ENDIF

      ! For polar projections, GAMMA = +1 (north) or -1 (south).
      IF (DLAT .GE. LATLMT) THEN
        ! near north pole. approximate 1.0 - sin(lat) as delta.
        EPS = (DLAT - 90.0) * RADPDG
        DELTA = 0.5*EPS*EPS
        IF (ABS(GAMMA) .LT. 0.001 .OR. DELTA .EQ. 0) THEN
          ETA = 1./STRCMP(1)
          XI = 0.
          RETURN
        ELSE
          RHOG1 = (1. - (0.5*DELTA)**( 0.5*GAMMA)) / GAMMA
        ENDIF
      ELSE IF (DLAT .LE. -LATLMT) THEN
        ! near south pole. approximate 1.0 + sin(lat) as delta.
        EPS = (DLAT + 90.0) * RADPDG
        DELTA = 0.5*EPS*EPS
        IF (ABS(GAMMA) .LT. 0.001 .OR. DELTA .EQ. 0) THEN
          ETA = 1./STRCMP(1)
          XI = 0.
          RETURN
        ELSE
          RHOG1 = (1. - (0.5*DELTA)**(-0.5*GAMMA)) / GAMMA
        ENDIF
      ELSE
        SLAT = SIN(RADPDG * DLAT)
        MERCY = .5 * LOG( (1. + SLAT) / (1. - SLAT) )
        GMERCY = GAMMA * MERCY
        IF (ABS(GMERCY) .LT. .001) THEN
!  CODE FOR GAMMA SMALL OR ZERO.  THIS AVOIDS ROUND-OFF ERROR OR DIVIDE-
!  BY ZERO IN THE CASE OF MERCATOR OR NEAR-MERCATOR PROJECTIONS.
          RHOG1 = MERCY * (1. - .5 * GMERCY *                                    &
                            (1. - 1./3. * GMERCY *                               &
                            (1. - 1./4. * GMERCY ) ) )
        ELSE
! CODE FOR MODERATE VALUES OF GAMMA
          RHOG1 = (1. - EXP(-GMERCY)) / GAMMA
        ENDIF
      ENDIF
      ETA = RHOG1 + (1. - GAMMA * RHOG1) * GAMMA * CSDGAM
      XI = (1. - GAMMA * RHOG1 ) * SNDGAM
      END SUBROUTINE
