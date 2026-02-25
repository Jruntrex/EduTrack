# EduTrack: UX Pilot Page Structure & Design Requirements

## 1. Global Design System (Aesthetic: "Corporate Premium Glass")
*   **Theme**: Modern, clean, and interactive. Use "Glassmorphism" (semi-transparent panels with background blur).
*   **Colors**:
    *   **Primary**: Indigo/Royal Blue (`#3B82F6` to `#4F46E5` gradients).
    *   **Secondary/Accent**: Emerald Green for success, Rose/Ruby for alerts/danger students.
    *   **Background**: Soft gradient or subtle mesh background (`bg-main-gradient`).
    *   **Panels**: `glass-panel` (white at 70% opacity, backdrop-blur 15px, 1px white border).
*   **Typography**: Sans-serif, bold tracking-tighter headers (`font-black`), capitalized utility text.
*   **Components**: Rounded corners (2xl to 3xl), subtle lift-up hover effects, pulse animations for live status.

---

## 2. Common Layout Structure
### **Sidebar (Fixed Left)**
*   **Logo**: EduTrack with dynamic icon.
*   **Nav Links**: Rounded icons (Heroicons style) with active state highlighting (gradient fill).
*   **User Logout**: Clean bottom-aligned action.
### **Header & Page Header**
*   **Navigation**: History back/forward buttons (glass style).
*   **Title**: Large, bold page title.
*   **User Menu (Right)**: Floating glass panel with:
    *   Notification bell with red dot.
    *   User Avatar (gradient circle) + Name + Role badge.
    *   Dropdown for Profile/Settings.

---

## 3. Page Breakdown

### **1. Login Page**
*   **Layout**: Centered glass card on a full-screen gradient background.
*   **Elements**: System logo, "Вхід до системи" text, Email/Password fields with icons, "УВІЙТИ" primary button.
*   **UX**: Smooth slide-up animations for form elements.

### **2. Admin Dashboard**
*   **KPI Grid**: 4-5 glass cards showing: Total Users, Students, Groups, Subjects, Classrooms.
*   **Quick Actions**: Large grid buttons with icons for "Add User", "Set Schedule", "Generate Reports".

### **3. Teacher Dashboard**
*   **Greeting**: "Привіт, [Name]! 👋" with current date.
*   **KPIs**: 
    *   Current Lessons (Large number card).
    *   Weekly Load progress bar.
    *   "Risk Radar" (Students needing attention, red pulse indicator).
*   **Timeline**: Vertical schedule for today with "Live Mode" entry buttons.
*   **Interactive**: "🎲 Інтерактив" - Random student picker widget at the bottom.

### **4. Student Dashboard**
*   **Performance Chart**: Area line chart showing grade dynamics (Chart.js style).
*   **Average Score**: Giant number display in a gradient card.
*   **Next Lesson**: Card highlighting "Right Now" or "Next Up" with teacher info and classroom.
*   **Attendance**: Doughnut chart showing Presence vs Absence.
*   **Recent Grades**: Table of the last few assessments.

### **5. Management Pages (Students / Users / Groups)**
*   **Toolbar**: Search bar + Filter dropdowns (Role, Group, Subject) in a glass bar.
*   **Action Button**: Floating "Add [Entity]" button.
*   **Data Table**: 
    *   Clean white header.
    *   Zebra-striped rows or hover-highlighted rows.
    *   Avatars/Initial circles for people.
    *   Badges for roles/statuses (Admin=Purple, Teacher=Blue, Student=Green).
    *   Inline actions (Edit/Delete) visible on row hover.

### **6. Teacher: Live Mode (Interactive Classroom)**
*   **Control Panel**:
    *   Lesson Topic edit field (underlined, focused).
    *   **🎲 Roulette**: Dynamic student picker button.
    *   **Countdown Timer**: Large digital clock, Start/Stop/Reset controls, input for session duration.
*   **Student Grid**: 
    *   Large "Seat" cards for each student.
    *   **Absent State**: Blurred overlay with "N" marker.
    *   **Grading**: Floating grade badge appears on card after assessment.
    *   **Live indicator**: Green dot if online.
### **7. Schedule (TimeLord)**
*   **Header**: Group/Week selector, "Edit" button for admins.
*   **Table**: Classic grid layout.
    *   Rows: Study periods (1-6).
    *   Columns: Days of week (Mon-Sat).
    *   Individual cells: Subject name, Greenhouse/Classroom badge, Teacher short name.

---

## 4. Interaction Guidelines
*   **Transitions**: All hover states should have `transition-all duration-300`.
*   **Modals**: Grading modal scales up with a backdrop blur. No sharp edges.
*   **Responsiveness**: Mobile view collapses sidebar into a hamburger menu; tables become scrollable or card-based lists.
