SUBROUTINE FCCLOS(HANDLE,*)

!-------------------------------------------------------------------------------
! Clean exit for all open units
! Last Revised: 06 Mar 2001
!               20 Oct 2021 (SYZ) - add IMPLICIT NONE and declare all variables
!-------------------------------------------------------------------------------
  IMPLICIT NONE

  INTEGER HANDLE

  CLOSE(HANDLE,ERR=900)
  RETURN

  900 RETURN 1

END SUBROUTINE fcclos
