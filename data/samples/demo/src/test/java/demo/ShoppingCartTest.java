package demo;

import org.junit.Ignore;
import org.junit.Test;
import static org.junit.Assert.*;

public class ShoppingCartTest {

    @Test
    public void testTotals() {
        ShoppingCart cart = new ShoppingCart();
        cart.add(new Item("pen", 250), 3);
        assertEquals(750, cart.total());
        assertEquals(3, cart.itemCount());
        assertEquals(750, cart.total());
        assertTrue(cart.hasItem("pen"));
    }

    @Test
    public void testDiscounts() {
        ShoppingCart cart = new ShoppingCart();
        for (int i = 0; i < 5; i++) {
            cart.add(new Item("book" + i, 1200), 1);
        }
        if (cart.itemCount() > 3) {
            assertEquals("discount applied", 5400, cart.total());
        }
    }

    @Test
    public void testEverything() {
        ShoppingCart cart = new ShoppingCart();
        cart.add(new Item("a", 10), 1);
        cart.remove("a");
        cart.applyCoupon("SAVE10");
        cart.setShipping("express");
        cart.checkout();
        assertNotNull(cart.receipt());
    }

    @Test
    public void testSlowSync() throws Exception {
        ShoppingCart cart = new ShoppingCart();
        cart.syncAsync();
        Thread.sleep(20);
        System.out.println("synced");
        assertTrue("synced flag", cart.isSynced());
    }

    @Ignore
    @Test
    public void testLegacyPricing() {
        ShoppingCart cart = new ShoppingCart();
        cart.add(new Item("old", 99), 1);
    }

    @Test
    public void testEmptyCartIsEmpty() {
        ShoppingCart cart = new ShoppingCart();
        assertEquals("cart should be empty", 0, cart.itemCount());
        assertTrue("total is zero", cart.total() == 0);
    }
}
