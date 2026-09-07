      INTERFACE
         SUBROUTINE SECT0(buff,klen,kptr,kret)
         IMPLICIT NONE
         CHARACTER(1), INTENT(IN)  :: BUFF(:)
         INTEGER,      INTENT(OUT) :: KLEN
         INTEGER,      INTENT(OUT) :: KPTR(:)
         INTEGER,      INTENT(OUT) :: KRET
         END SUBROUTINE sect0

         SUBROUTINE SECT1(buff,klen,kpds,kptr)
         IMPLICIT NONE
         CHARACTER(1), INTENT(IN)  :: BUFF(:)
         INTEGER,      INTENT(OUT) :: KLEN
         INTEGER,      INTENT(OUT) :: KPDS(:)
         INTEGER,      INTENT(OUT) :: KPTR(:)
         END SUBROUTINE sect1

         SUBROUTINE SECT2(buff,klen,kgds,kptr,kret)
         IMPLICIT NONE
         CHARACTER(1), INTENT(IN)  :: BUFF(:)
         INTEGER,      INTENT(OUT) :: KLEN
         INTEGER,      INTENT(OUT) :: KGDS(:)
         INTEGER,      INTENT(OUT) :: KPTR(:)
         INTEGER,      INTENT(OUT) :: KRET    
         END SUBROUTINE sect2

         SUBROUTINE SECT3(buff,klen,kptr)
         IMPLICIT NONE
         CHARACTER(1), INTENT(IN)  :: BUFF(:)
         INTEGER,      INTENT(OUT) :: KLEN
         INTEGER,      INTENT(OUT) :: KPTR(:)
         END SUBROUTINE sect3

         SUBROUTINE SECT4(buff,klen,kptr,mfact,refval,nbpv,kret)
         IMPLICIT NONE
         CHARACTER(1), INTENT(IN)  :: BUFF(:)
         INTEGER,      INTENT(OUT) :: KLEN
         INTEGER,      INTENT(OUT) :: KPTR(:)
         INTEGER,      INTENT(OUT) :: MFACT
         REAL,         INTENT(OUT) :: REFVAL
         INTEGER,      INTENT(OUT) :: NBPV
         INTEGER,      INTENT(OUT) :: KRET
         END SUBROUTINE sect4

         SUBROUTINE SECT5(buff,klen,kret)
         IMPLICIT NONE
         CHARACTER(1), INTENT(IN)  :: BUFF(:)
         INTEGER,      INTENT(OUT) :: KLEN
         INTEGER,      INTENT(OUT) :: KRET
         END SUBROUTINE sect5

         SUBROUTINE DECODE(bmap,buff,kbms,rvar,nxyp,kfact,mfact,refval,nbpv)
         IMPLICIT NONE
         CHARACTER(1), INTENT(IN)  :: BMAP(:)
         CHARACTER(1), INTENT(IN)  :: BUFF(:)
         LOGICAL(1),   INTENT(OUT) :: KBMS(:)
         REAL,         INTENT(OUT) :: RVAR(:)
         INTEGER,      INTENT(IN)  :: NXYP
         INTEGER,      INTENT(IN)  :: KFACT
         INTEGER,      INTENT(IN)  :: MFACT
         REAL,         INTENT(IN)  :: REFVAL
         INTEGER,      INTENT(IN)  :: NBPV
         END SUBROUTINE decode
      END INTERFACE
