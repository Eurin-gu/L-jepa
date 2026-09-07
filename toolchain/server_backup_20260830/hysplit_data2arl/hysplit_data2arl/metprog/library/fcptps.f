SUBROUTINE FCPTPS(HANDLE,NBYTE,*)

!-------------------------------------------------------------------------------
! Sets byte and record pointers within the data buffer.  The value of NBYTE is 
! assumed to be the last byte read, therefore the next read will be at NBYTE+1.
! Last Revised: 06 Mar 2001
!               03 Mar 2011 - INT function for krec not required
!               20 Oct 2021 - add IMPLICIT NONE and declare all variables
!-------------------------------------------------------------------------------
  IMPLICIT NONE

  INTEGER HANDLE
  INTEGER NBYTE
  COMMON /KINDEX/ KBYTE(90), KREC(90), KBUFLEN
  INTEGER KBYTE,KREC,KBUFLEN

! compute record number assuming buffer length
  KREC(HANDLE)=(NBYTE/KBUFLEN)+1
  IF(KREC(HANDLE).LT.1)THEN
     WRITE(*,*)'ERROR fcptps: position to record - ',KREC(HANDLE)
     RETURN 1
  END IF

! compute next byte position to read within buffer
  KBYTE(HANDLE)=MOD(NBYTE,KBUFLEN)+1

END SUBROUTINE fcptps
