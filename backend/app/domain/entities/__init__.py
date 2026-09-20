"""领域实体包（`05-domain-model.md` §1.2）。共 14 个实体类（含抽象基类与全部子类）。"""

from app.domain.entities.book_title import BookTitle
from app.domain.entities.borrow_card import BorrowCard
from app.domain.entities.fine_record import FineRecord
from app.domain.entities.library_item import Book, LibraryItem, Magazine, Thesis
from app.domain.entities.loan import Loan
from app.domain.entities.reader import Librarian, Reader, StudentReader, SystemAdmin, TeacherReader
from app.domain.entities.reservation import Reservation

__all__ = [
    "Book",
    "BookTitle",
    "BorrowCard",
    "FineRecord",
    "Librarian",
    "LibraryItem",
    "Loan",
    "Magazine",
    "Reader",
    "Reservation",
    "StudentReader",
    "SystemAdmin",
    "TeacherReader",
    "Thesis",
]
