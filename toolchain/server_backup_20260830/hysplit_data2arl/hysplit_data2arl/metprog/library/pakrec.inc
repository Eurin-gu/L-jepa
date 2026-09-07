INTERFACE
  SUBROUTINE PAKREC(LUNIT,RVAR,CVAR,NX,NY,NXY,KVAR,IY,IM,ID,IH,MN,IC,LL,KINI)
  IMPLICIT NONE
  INTEGER,      INTENT(IN)    :: LUNIT       ! output unit number
  REAL,         INTENT(IN)    :: RVAR(NX,NY) ! input data to be packed
  CHARACTER(1), INTENT(INOUT) :: CVAR(NXY)   ! packed data array
  INTEGER,      INTENT(IN)    :: NX,NY       ! dimensions of RVAR
  INTEGER,      INTENT(IN)    :: NXY         ! dimensions of CVAR
  CHARACTER(4), INTENT(IN)    :: KVAR        ! descriptor of variable written
  INTEGER,      INTENT(IN)    :: IY,IM,ID    ! date identification
  INTEGER,      INTENT(IN)    :: IH,MN       ! time identification (MN-minutes)
  INTEGER,      INTENT(IN)    :: IC          ! forecast hour, ICX hour for >99
  INTEGER,      INTENT(IN)    :: LL          ! level indicator 
  INTEGER,      INTENT(IN)    :: KINI        ! initialization (0-no 1-yes)
  END SUBROUTINE
END INTERFACE
