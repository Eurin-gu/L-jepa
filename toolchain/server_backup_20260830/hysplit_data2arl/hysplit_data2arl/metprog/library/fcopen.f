INTEGER FUNCTION FCOPEN(FNAME,MODE)

!-------------------------------------------------------------------------------
! Opens FNAME for input or output depending upon MODE string
!------------------------------------------------------------------------------
! PROGRAM HISTORY LOG:
!   LAST REVISED: 06 Mar 2001
!                 25 Feb 2011 - check unit numbers from 11 on with each entry
!                 20 Oct 2021 - add IMPLICIT NONE and declare all variables
!                 18 Oct 2022 - include/declare subroutine interfaces
!-------------------------------------------------------------------------------
  IMPLICIT NONE

  INCLUDE 'fcptps.inc'
 
  LOGICAL FTEST
  CHARACTER FNAME*(*),MODE*(*)
  COMMON /KINDEX/ KBYTE(90), KREC(90), KBUFLEN
  INTEGER KBYTE,KREC,KBUFLEN
  integer kunit

  KBUFLEN=2048
  KUNIT=10

  FTEST=.TRUE.
  DO WHILE (FTEST.AND.KUNIT.LE.90)
     KUNIT=KUNIT+1
!    find the next available unit number
     INQUIRE(KUNIT,OPENED=FTEST) 
  END DO

  IF(KUNIT.GT.90)THEN
     WRITE(*,*)'ERROR fcopen: too many files have been opened - ',KUNIT
     FCOPEN=-1
     RETURN
  END IF

  IF(MODE(1:1).EQ.'r'.OR.MODE(1:1).EQ.'R')THEN
     OPEN(UNIT=KUNIT,FILE=FNAME,FORM='UNFORMATTED',ACCESS='DIRECT',            &
          RECL=KBUFLEN,ACTION='READ')
  ELSEIF(MODE(1:1).EQ.'w'.OR.MODE(1:1).EQ.'W')THEN
     OPEN(UNIT=KUNIT,FILE=FNAME,FORM='UNFORMATTED',ACCESS='DIRECT',            &
          RECL=KBUFLEN,ACTION='WRITE')
  ELSEIF(MODE(1:2).EQ.'rw'.OR.MODE(1:2).EQ.'RW')THEN
     OPEN(UNIT=KUNIT,FILE=FNAME,FORM='UNFORMATTED',ACCESS='DIRECT',            &
          RECL=KBUFLEN,ACTION='READWRITE')
  ELSE
     WRITE(*,*)'ERROR fcopen: invalid mode selection - ',MODE
     FCOPEN=-1
     RETURN
  END IF

  FCOPEN=KUNIT
! initialize all pointers to the beginning of each file
  CALL FCPTPS(KUNIT,0,*100)
  RETURN

  100 STOP 

END FUNCTION fcopen
