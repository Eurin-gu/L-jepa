INTERFACE
   SUBROUTINE PAKINI(KG,CVAR,NXY)
      IMPLICIT NONE
      INTEGER,      INTENT(IN)  :: kg         ! current active grid number
      CHARACTER(1), INTENT(OUT) :: cvar(nxy)  ! packed data array
      INTEGER,      INTENT(IN)  :: nxy        ! dimension of packed data
   END SUBROUTINE
END INTERFACE
